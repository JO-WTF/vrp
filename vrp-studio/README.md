# VRP Studio

VRP Studio 是一个用于展示和调试 VRP 求解过程的可视化服务。


## 一键编译部署

如果你希望一次性完成后端依赖安装、`vrp-cli` Python 绑定构建、前端构建，并将前端静态资源部署到后端包中，可以在仓库根目录执行：

```bash
./vrp-studio/deploy.sh
```

Windows:

```powershell
.\vrp-studio\deploy.ps1
```

默认会在完成构建后启动服务，访问地址为：`http://127.0.0.1:8000`。常用参数：

```bash
./vrp-studio/deploy.sh --clean --port 8000
./vrp-studio/deploy.sh --no-start
```

Windows:

```powershell
.\vrp-studio\deploy.ps1 -Clean -Port 8000
.\vrp-studio\deploy.ps1 -NoStart
```

脚本会执行以下步骤：

1. 创建或复用仓库根目录下的 `.venv`。
2. 安装 `vrp-studio/requirements.txt` 中的后端依赖。
3. 调用仓库根目录的构建脚本安装本地 `vrp-cli` Python 绑定。
4. 在 `vrp-studio/frontend` 中执行 `npm ci`/`npm install` 和 `npm run build`。
5. 将 `vrp-studio/frontend/dist` 复制到 `vrp-studio/vrp_studio/frontend/dist`，供 FastAPI 后端托管。


## 后端地址配置

前端会在启动时加载 `/config.js`。该文件来自 `vrp-studio/frontend/public/config.js`，构建后会被复制到前端产物根目录，用于配置浏览器访问后端服务的地址和端口。

默认配置使用当前访问前端的域名和端口，适合前后端由同一个 FastAPI 服务托管的场景：

```js
window.VRP_STUDIO_CONFIG = {
  API_BASE_URL: "",
  WS_BASE_URL: "",
  BACKEND_PROTOCOL: window.location.protocol.replace(/:$/, ""),
  BACKEND_HOST: window.location.hostname,
  BACKEND_PORT: window.location.port,
}
```

如果前端通过域名访问，但后端部署在另一个域名或端口，可以直接修改部署后的 `config.js`：

```js
window.VRP_STUDIO_CONFIG = {
  API_BASE_URL: "https://vrp-api.example.com:8000",
  WS_BASE_URL: "wss://vrp-api.example.com:8000",
}
```

也可以使用拆分字段配置：

```js
window.VRP_STUDIO_CONFIG = {
  BACKEND_PROTOCOL: "https",
  BACKEND_HOST: "vrp-api.example.com",
  BACKEND_PORT: "8000",
}
```


如果前端和后端不在同一个 origin，可以通过环境变量限制允许访问后端的前端域名：

```bash
VRP_STUDIO_CORS_ORIGINS=https://studio.example.com uv run --python .venv/bin/python vrp-studio --port 8000
```

多个域名用逗号分隔；默认值为 `*`，方便本地调试。

## 启动说明

### 1) 安装依赖

在仓库根目录执行（推荐使用 `uv`）：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r vrp-studio/requirements.txt
```

或者使用 `pip`：

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r vrp-studio/requirements.txt
```

### 2) 安装/构建 vrp-cli（Python 绑定）

如果本地尚未安装可用的 `vrp-cli`，先在仓库根目录执行：

```bash
./build.sh --no-rust
```

Windows:

```powershell
.\build.ps1 -NoRust
```

### 3) 启动服务

在仓库根目录执行：

```bash
uv run --python .venv/bin/python vrp-studio --port 8000
```

Windows:

```powershell
uv run --python .venv\Scripts\python.exe vrp-studio --port 8000
```

如果你已经激活了虚拟环境，也可以直接使用：

```bash
.venv/bin/vrp-studio --port 8000
```

启动后可在浏览器访问：`http://127.0.0.1:8000`。
