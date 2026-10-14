# LZ-Alt30

老赵基本面山寨指数。30 个 BTC 之外的资产以 USD 现货价格等权初始化。正式指数于 **2026-10-13** 从 **1000 点**起算，季度首日按旧持仓估值后恢复等权。

网页：<https://zhaotools.github.io/LZ-Alt30/>

数据来源：[DefiLlama Coins API](https://api-docs.defillama.com/llms-free.txt)

## 页面边界

- `site/` 是 GitHub Pages 发布目录。正式指数与基日前的历史参考分区展示。
- 历史参考窗口为 2025-10-14 至 2026-10-13，使用当前 30 币名单回推；它不是正式指数历史业绩，不随之后的每日采样延长。
- BTC 和 ETH 在历史参考中以 2025-10-14 为 1000 的对照起点。正式指数中的比较序列另以 2026-10-13 为 1000，不能混用。
- 页面研究文字为 2026-10-13 的快照；每日只更新价格及其衍生指标。成分复审须单独研究、公告和留档。

## 数据与计算

- `research/指数说明与选币分析.md` 是用户提供的原始说明，未改写。原始 ZIP 留在本地研究目录，不发布到公开仓库。
- `scripts/calculate_index.py` 是附件中的原始计算器；`data/daily_prices.csv`、`data/quote_times.csv`、`data/constituents.json` 从附件提取，随后由定时任务追加日度记录。
- `data/attachment_index_values.csv` 保存附件当时的复算结果，供初始核验。
- `scripts/build_site.py` 生成 `site/data/index.json`。网站不直接查询外部行情 API，展示与 Git 中留存的数据一致。
- `scripts/update_prices.py` 每次向 DefiLlama 查询缺失日期的 31 个资产。任何缺失、非正价格、重复日期或距离 UTC 零点超过 15 分钟的报价都会使任务失败；失败时不提交新数据，线上保留上次有效版本。

## 本地运行

```sh
python3 scripts/build_site.py
python3 -m unittest discover -s tests -v
python3 -m http.server 8000 --directory site
```

访问 <http://localhost:8000/>。手动补采样可运行 `python3 scripts/update_prices.py --date YYYY-MM-DD`；程序从当前最后日期逐日补齐到目标 UTC 日期，不改写已有采样。

## 自动发布

`.github/workflows/publish.yml` 在每日 **01:17 UTC（北京时间 09:17）**运行，也支持手动触发。通过验证后，它把新价格、报价时间和网页数据提交到 `main`，并在同一次工作流中部署 Pages。GitHub 定时任务可能延迟；页面以“采样日期”和数据状态为准。

此指数仅用于研究观察，不含质押、锁仓、空投、借贷、资金费或交易成本，不构成投资建议。
