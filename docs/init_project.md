# 项目基础设计文档（精简版）

## 1. 项目目标

实现一个**最简单的前后端一体化项目**，用于验证基础环境连通性。

功能流程：

1. 用户打开首页
2. 页面上有一个按钮
3. 点击按钮后调用后端接口
4. 后端从 `data/hello.txt` 读取文本内容
5. 将读取结果返回前端
6. 前端把结果显示在页面上

`hello.txt` 的内容固定为：

```text
hello world
```

---

## 2. 技术要求

* 使用 **FastAPI + Jinja2 + HTMX**
* 不使用 React
* 不使用前后端分离
* 不引入数据库业务逻辑
* 不引入 Redis、Celery、PostgreSQL、Nginx 等额外组件
* 项目必须能通过 **Docker Compose** 启动
* 数据目录必须持久化保存在宿主机项目目录中
* 容器必须通过挂载方式访问宿主机 `data` 目录

---

## 3. 项目结构

目标目录结构如下：

```text
project-root/
├─ app/
│  ├─ main.py
│  ├─ routes/
│  │  ├─ pages.py
│  │  └─ api.py
│  ├─ services/
│  │  └─ file_service.py
│  ├─ templates/
│  │  ├─ base.html
│  │  └─ index.html
│  └─ static/
│     ├─ css/
│     └─ js/
├─ data/
│  └─ hello.txt
├─ docker/
│  └─ Dockerfile
├─ compose.yaml
├─ requirements.txt
└─ .env
```

---

## 4. 页面要求

项目只包含一个页面：首页 `/`

页面必须包含：

* 一个标题
* 一段简短说明
* 一个按钮
* 一个结果显示区域

页面初始时结果区域为空，或显示“尚未读取”。

点击按钮后：

* 调用后端接口
* 成功时显示返回文本
* 失败时显示错误信息

页面风格只要求简洁清晰，不需要复杂 UI。

---

## 5. 路由要求

### 页面路由

* `GET /`
* 返回首页 HTML

### 接口路由

* `GET /api/hello`
* 从 `data/hello.txt` 读取内容并返回 JSON

成功返回示例：

```json
{
  "success": true,
  "content": "hello world"
}
```

失败返回示例：

```json
{
  "success": false,
  "error": "读取文件失败"
}
```

---

## 6. 文件读取要求

* 后端必须真实读取文件
* 不允许把 `hello world` 写死在代码里
* 文件路径来源于挂载后的 `data` 目录
* 文件使用 UTF-8 编码读取

---

## 7. Docker 与持久化要求

使用 Docker Compose 启动项目。

宿主机项目目录中的：

```text
./data
```

必须挂载到容器内，例如：

```text
/app/data
```

要求后端从容器内挂载路径读取文件，例如：

```text
/app/data/hello.txt
```

这样可以保证：

* 数据持久化保存在宿主机
* 容器能读取宿主机目录
* 后续图片和素材也可沿用同样方式存储

---

## 8. 分层要求

虽然当前功能极简单，仍然要求最基本分层：

* `pages.py`：页面路由
* `api.py`：接口路由
* `file_service.py`：文件读取逻辑

不要把所有逻辑都堆在入口文件中。

---

## 9. 明确约束

### 必须满足

1. 生成一个最小可运行项目
2. 使用 FastAPI + Jinja2 + HTMX
3. 只有一个首页和一个按钮
4. 点击按钮后调用后端接口
5. 后端必须从 `data/hello.txt` 读取内容
6. 前端必须显示后端返回结果
7. Docker Compose 必须挂载宿主机 `data` 目录

### 不要做

1. 不要引入 React
2. 不要做前后端分离
3. 不要增加复杂业务功能
4. 不要引入多服务复杂架构
5. 不要过度设计文件系统
6. 不要把 `hello world` 写死在接口返回中

---

## 10. 验收标准

完成后必须满足以下检查：

1. 宿主机存在 `data/hello.txt`
2. 文件内容为 `hello world`
3. 启动 Docker Compose 后可访问首页
4. 页面能看到按钮
5. 点击按钮后页面显示 `hello world`
6. 修改宿主机 `data/hello.txt` 内容后，再次点击按钮，页面显示新内容

最后一条用于证明后端确实读取的是宿主机挂载文件，而不是写死值。


