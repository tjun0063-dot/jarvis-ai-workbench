"""Copy only explicitly listed files from this task's Muse output directory."""
import base64
import json
from pathlib import Path, PurePosixPath
import re

FILE_LIMIT = 100 * 1024 * 1024
TASK_LIMIT = 300 * 1024 * 1024


def safe_name(value):
    if (not isinstance(value,str) or not value or len(value)>180
            or re.search(r'[<>:"/\\|?*\x00-\x1f]',value) or value.endswith(('.', ' '))
            or re.match(r'^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)',value,re.I)
            or value in ('.','..')):
        raise ValueError('Muse 附件文件名无效')
    return value


def remote_path(value, task_id):
    if not isinstance(value,str) or '\\' in value or '\x00' in value:
        raise ValueError('Muse 附件路径无效')
    for prefix in ('/home/hatch/','~/','/'):
        if value.startswith(prefix):
            value=value[len(prefix):]
            break
    parts=PurePosixPath(value).parts
    if (len(parts)<3 or len(parts)>8 or parts[:2]!=('.jarvis-outbox',task_id)
            or any(p in ('.','..') for p in value.split('/'))):
        raise ValueError('Muse 附件超出本次任务输出目录')
    return str(PurePosixPath(*parts))


def attachment_list(text, task_id):
    files=[]
    def take(match):
        doc=json.loads(match.group(1))
        rows=doc.get('files')
        if not isinstance(rows,list):raise ValueError('Muse 附件清单无效')
        for row in rows:
            source=remote_path(row.get('path'),task_id)
            name=safe_name(row.get('name') or PurePosixPath(source).name)
            files.append({'path':source,'name':name})
        return ''
    cleaned=re.sub(r'```workbench-artifacts\s*\n([\s\S]*?)```',take,text).strip()
    if '```workbench-artifacts' in cleaned:raise ValueError('Muse 附件清单未完整返回')
    if len(files)>20 or len({f['name'].casefold() for f in files})!=len(files):
        raise ValueError('Muse 附件超过 20 个或文件名重复')
    return cleaned,files


def download(gateway, files, destination):
    destination=Path(destination)
    if not destination.is_dir() or destination.resolve()!=destination.absolute():
        raise ValueError('本机附件输出目录无效')
    total=0
    for item in files:
        info=gateway.call_json('fs.stat',body={'path':item['path']})
        size=info.get('size')
        if info.get('kind')!='file' or type(size) is not int or not 0<=size<=FILE_LIMIT:
            raise ValueError('Muse 附件不是普通文件或超过 100MB')
        total+=size
        if total>TASK_LIMIT:raise ValueError('Muse 附件总计超过 300MB')
        target=destination/safe_name(item['name'])
        staged=target.with_name(target.name+'.muse-part')
        offset=0
        try:
            with staged.open('xb') as stream:
                while offset<size:
                    count=min(1024*1024,size-offset)
                    result=gateway.call_json('fs.read',body={'path':item['path'],'offset':offset,'len':count})
                    encoded=result.get('data_base64')
                    if not isinstance(encoded,str) or len(encoded)>1400000:
                        raise ValueError('Muse 原始文件分块无效')
                    raw=base64.b64decode(encoded,validate=True)
                    if (result.get('offset')!=offset or result.get('len')!=len(raw)
                            or not raw or len(raw)>count or (result.get('eof') and offset+len(raw)!=size)):
                        raise ValueError('Muse 原始文件分块长度不一致')
                    stream.write(raw)
                    offset+=len(raw)
            # Do not overwrite another deliverable if names conflict.
            if target.exists():raise ValueError('Muse 附件文件名重复')
            staged.rename(target)
        finally:
            if staged.exists():staged.unlink()
