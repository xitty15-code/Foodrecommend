# 部署说明

本项目推荐部署到 Railway。Flask 会同时提供前端页面和 `/api/*` 接口，因此只需要一个 Web 服务和一个 MySQL 服务。

## Railway 部署

1. 将仓库推送到 GitHub。
2. 在 Railway 新建项目，选择 `Deploy from GitHub repo`，导入本仓库。
3. 在同一 Railway 项目中添加 MySQL 服务。
4. 打开 Web 服务的 `Variables`，添加 MySQL 服务的变量引用。优先引用 `MYSQL_URL`；也可以引用 `MYSQLHOST`、`MYSQLPORT`、`MYSQLUSER`、`MYSQLPASSWORD`、`MYSQLDATABASE`。
5. 为 Web 服务新增变量：

   ```text
   SECRET_KEY=换成一段足够长的随机字符串
   SESSION_COOKIE_SECURE=true
   ```

6. 触发部署。`railway.json` 会使用根目录 `Dockerfile` 构建服务，部署前执行 `python backend/crawl_allmenus_food_data.py`，自动建表并导入仓库内的 `backend/data/chinese_food_caption.csv`。
7. 部署完成后在 Railway 为 Web 服务生成域名，访问该域名即可打开首页。

## 验收检查

- 访问首页能正常显示推荐内容。
- 访问 `/api/health` 返回 `success: true`。
- 注册一个新用户，登录后刷新页面仍能继续访问个人中心。
- 打开全部美食、详情页、收藏或评论流程，确认数据库写入正常。

## 本地与其他平台

本地开发仍可使用原来的变量名：

```text
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=123456
DB_NAME=food_db
```

也可以只提供 `MYSQL_URL` 或 `DATABASE_URL`。如果换到其他支持 Docker 和 MySQL 的平台，保持这些数据库变量一致即可。
