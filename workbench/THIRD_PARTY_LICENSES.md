微信协议实现参考 XavierJiezou/codex-weixin：

MIT License

Copyright (c) 2026 Xuechao Zou

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


## wxauto4

安装依赖：PyPI wxauto4 41.1.7（作者 Cluic），仅作为运行依赖使用，未将其源码复制到工作台。依赖的分发及许可遵循该包及作者条款；不声明它是 MIT 授权。安装环境不包含在源码交付中。

包页面：https://pypi.org/project/wxauto4/
作者文档及条款：https://docs.wxauto.org/docs/install.html

连接设计参考：wxauto4 的 AddListenChat / GetSession / ChatInfo 接口文档，以及 https://github.com/fly000001/wxauto4 的公开示例。wechat_assistant.py 与 remote.mjs 是工作台自身适配代码。


## muse.ai personal agent adapter (2026-10-16)

Muse CLI 0.3.2: https://github.com/nikships/muse-cli (MIT). Installed wheel and bundled license reside under .muse-venv/Lib/site-packages.

Vercel agent-browser 0.39.1: https://github.com/vercel-labs/agent-browser (Apache-2.0). Installed through npm in tools/personal-muse-browser; license and notices remain in the package. Used only for the person-approved, one-time local Muse session transfer.
