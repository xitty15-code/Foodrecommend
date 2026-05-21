# 数据集来源说明

本项目的菜品数据使用真实公开数据集导入，不伪造、不模拟记录。

## 当前来源

- 来源名称：Hugging Face Dataset `zmao/chinese_food_caption`
- 数据集页：https://huggingface.co/datasets/zmao/chinese_food_caption
- 数据获取接口：https://datasets-server.huggingface.co/rows
- 导入脚本：`backend/crawl_allmenus_food_data.py`

该数据集提供真实中文菜品图文样本。导入脚本会优先保留中文菜品记录，并过滤明显的国外菜品关键词，尽量保证项目数据更符合“校园美食推荐”的定位。

此外，脚本还会合并 `backend/data/xiasha_enrichment.json` 中整理的浙江杭州下沙大学城周边真实门店菜单信息，用于补充价格、评分、简介和来源说明，确保项目更贴近校园周边小餐馆场景。

图片字段优先保留数据集里的真实图片地址；本地门店补充记录会复用真实菜品图片池，不会凭空生成图片。

## 导入方式

在项目根目录执行：

```bash
cd backend
python crawl_allmenus_food_data.py --replace
```

如果你只想追加导入，不清空旧数据：

```bash
cd backend
python crawl_allmenus_food_data.py
```

导入脚本会先收集真实数据，再写入 MySQL 的 `food_db.food` 表。若使用 `--replace`，会同时清空 `user_history`、`user_favorite`、`user_review`，避免旧记录指向已删除菜品。
