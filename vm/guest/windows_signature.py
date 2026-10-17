"""Authenticode trust, verified signer and file version through Windows APIs.

Uses the documented WinVerifyTrust lifecycle, with normal Authenticode policy.
No PowerShell modules or execution-policy changes are involved.
"""
import ctypes as c
from pathlib import Path
import uuid

DWORD = c.c_uint32
VOID = c.c_void_p


class GUID(c.Structure):
    _fields_ = [('Data1', DWORD), ('Data2', c.c_uint16), ('Data3', c.c_uint16),
                ('Data4', c.c_ubyte * 8)]


class FileInfo(c.Structure):
    _fields_ = [('cbStruct', DWORD), ('pcwszFilePath', c.c_wchar_p),
                ('hFile', VOID), ('pgKnownSubject', VOID)]


class TrustData(c.Structure):
    _fields_ = [('cbStruct', DWORD), ('pPolicyCallbackData', VOID), ('pSIPClientData', VOID),
                ('dwUIChoice', DWORD), ('fdwRevocationChecks', DWORD), ('dwUnionChoice', DWORD),
                ('pFile', c.POINTER(FileInfo)), ('dwStateAction', DWORD), ('hWVTStateData', VOID),
                ('pwszURLReference', c.c_wchar_p), ('dwProvFlags', DWORD), ('dwUIContext', DWORD),
                ('pSignatureSettings', VOID)]


class ProviderCertPrefix(c.Structure):
    # Only these documented initial fields are read from the full native object.
    _fields_ = [('cbStruct', DWORD), ('pCert', VOID)]


def file_version(path):
    version = c.WinDLL('version.dll', use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [c.c_wchar_p, c.POINTER(DWORD)]
    version.GetFileVersionInfoSizeW.restype = DWORD
    version.GetFileVersionInfoW.argtypes = [c.c_wchar_p, DWORD, DWORD, VOID]
    version.GetFileVersionInfoW.restype = c.c_int32
    version.VerQueryValueW.argtypes = [VOID, c.c_wchar_p, c.POINTER(VOID), c.POINTER(DWORD)]
    version.VerQueryValueW.restype = c.c_int32
    ignored = DWORD()
    size = version.GetFileVersionInfoSizeW(str(path), c.byref(ignored))
    if not size:
        return ''
    data = c.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, data):
        raise c.WinError(c.get_last_error())
    pointer, length = VOID(), DWORD()
    if not version.VerQueryValueW(data, '\\', c.byref(pointer), c.byref(length)) or length.value < 52:
        raise RuntimeError('无法读取程序版本。')
    fixed = c.cast(pointer, c.POINTER(DWORD * 13)).contents
    if fixed[0] != 0xFEEF04BD:
        raise RuntimeError('程序版本资源无效。')
    return '.'.join(map(str, [fixed[2] >> 16, fixed[2] & 0xFFFF, fixed[3] >> 16, fixed[3] & 0xFFFF]))


def signed_file_info(path):
    path = Path(path).resolve(strict=True)
    wintrust = c.WinDLL('wintrust.dll', use_last_error=True)
    crypt = c.WinDLL('crypt32.dll', use_last_error=True)
    wintrust.WinVerifyTrust.argtypes = [VOID, c.POINTER(GUID), c.POINTER(TrustData)]
    wintrust.WinVerifyTrust.restype = c.c_int32
    wintrust.WTHelperProvDataFromStateData.argtypes = [VOID]
    wintrust.WTHelperProvDataFromStateData.restype = VOID
    wintrust.WTHelperGetProvSignerFromChain.argtypes = [VOID, DWORD, c.c_int32, DWORD]
    wintrust.WTHelperGetProvSignerFromChain.restype = VOID
    wintrust.WTHelperGetProvCertFromChain.argtypes = [VOID, DWORD]
    wintrust.WTHelperGetProvCertFromChain.restype = c.POINTER(ProviderCertPrefix)
    crypt.CertGetNameStringW.argtypes = [VOID, DWORD, DWORD, VOID, c.c_wchar_p, DWORD]
    crypt.CertGetNameStringW.restype = DWORD
    action = GUID.from_buffer_copy(uuid.UUID('00aac56b-cd44-11d0-8cc2-00c04fc295ee').bytes_le)
    file = FileInfo(c.sizeof(FileInfo), str(path), None, None)
    trust = TrustData()
    trust.cbStruct = c.sizeof(TrustData)
    trust.dwUIChoice = 2  # WTD_UI_NONE: verification never prompts the user.
    trust.dwUnionChoice = 1  # WTD_CHOICE_FILE
    trust.pFile = c.pointer(file)
    trust.dwStateAction = 1  # WTD_STATEACTION_VERIFY
    # Zero provider flags preserve the normal Authenticode policy and timestamp checks.
    try:
        status = wintrust.WinVerifyTrust(VOID(-1), c.byref(action), c.byref(trust))
        if status != 0:
            raise RuntimeError('Windows 数字签名验证失败：' + path.name +
                               '（代码 0x' + format(status & 0xFFFFFFFF, '08X') + '）')
        provider = wintrust.WTHelperProvDataFromStateData(trust.hWVTStateData)
        if not provider:
            raise RuntimeError('无法读取已验证的签名状态。')
        signer = wintrust.WTHelperGetProvSignerFromChain(provider, 0, 0, 0)
        if not signer:
            raise RuntimeError('无法读取已验证的签名人。')
        cert = wintrust.WTHelperGetProvCertFromChain(signer, 0)
        if not cert or cert.contents.cbStruct < c.sizeof(ProviderCertPrefix) or not cert.contents.pCert:
            raise RuntimeError('无法读取已验证的签名证书。')
        size = crypt.CertGetNameStringW(cert.contents.pCert, 4, 0, None, None, 0)
        if size <= 1:
            raise RuntimeError('已验证的签名证书没有发布者名称。')
        name = c.create_unicode_buffer(size)
        if crypt.CertGetNameStringW(cert.contents.pCert, 4, 0, None, name, size) != size:
            raise RuntimeError('读取签名发布者名称失败。')
        return {'status': 'Valid', 'signer': name.value, 'version': file_version(path)}
    finally:
        trust.dwStateAction = 2  # Every verification state is closed, including failures.
        wintrust.WinVerifyTrust(VOID(-1), c.byref(action), c.byref(trust))
