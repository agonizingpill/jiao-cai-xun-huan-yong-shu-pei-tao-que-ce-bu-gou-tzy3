# 循书校园 · 循环用书配套与缺册补购

循书校园服务站有5位库管，服务12个班级。过去回收书按捆记数量，版本兼容凭经验，学生押金在班主任表格里：同科旧版有时缺章节却混入配套；缺册重复开采购单；退换和损耗没有单本条码，期末容易给未还书学生提前退款。这里从实际回收书况、教师版次核验，经过班级配套/缺册补购、学生领用退换，形成可核对的学期押金流水。上游是教师课程清单、回收条码和书况检查；下游是班级发书、采购库管与学生退款登记。

Python3.12 FastAPI、原生HTML/CSS/JS ES modules、MySQL8 READ COMMITTED、Redis和Python worker、Nginx，恰好5服务。

## 启动与账号

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

前端 http://localhost:18237 ，API http://localhost:19237/docs ，数据库17737；短名book-circulation，子网10.221.38.0/24。`.env.example`配置端口、JWT、短名、seed和网络。停止`docker compose down`，清空演示数据`docker compose down -v --remove-orphans`。

|岗位|邮箱 / 统一口令 Books2026!|权限|
|---|---|---|
|operator 用书库管|operator@xunshu.demo|登记版次/兼容申请/班级学生/回收书况/配套，分析共需，建立学期账户，学生领用/退书/换书|
|supervisor 书站主管|supervisor@xunshu.demo|全部日常动作；批准兼容、锁库存配套、采购到货、押金实收、报损扣款、期末清算|
|viewer 查阅席|viewer@xunshu.demo|六页面与档案/审计读取；所有写接口后端403|

JWT8小时，PBKDF2盐化口令；Trace请求ID、Burst每IP每分钟360请求、审计actor/action。默认JWT与数据库口令仅用于本地演示，部署时替换。

## 六个模块与领域规则

1. **版次兼容与课程清单**：Edition有唯一版本码、课程subject、版本、每册押金。Compatibility是明确方向“allowed旧版可代target课程版”，仅同课程不同版次可申请，主管批准才算兼容；不做传递推断。班级和学生有独立关系实体。一个配套同subject只能一条课程，不能用多个版次重复要求同科。
2. **回收书况和可用库存**：Copy唯一条码，关联实际版次；回收默认uninspected。Inspection保存检查历史，usable成为available，repair成为待修；修好后再检查可恢复。预留/在借/遗失书不允许直接覆盖书况。库存按单本状态计算，不用无依据的总数加减。
3. **班级配套与共需规则**：Pack关联班级/学期，PackLine要求课程版次和数量（≤班级人数）。Apriori提供历史课程共需建议，不自动加入课程或直接发书。planned→partial或allocated；每条PackLine按唯一Copy生成Assignment，保留配套、单本和学生的关系。
4. **领用分配和缺册补购**：主管配套先按固定ID顺序锁全部Edition，再取兼容、usable、available单本，原子改为reserved。数量不足形成该Line唯一Purchase缺册订单，不负库存；到货按新条码逐本入库，可部分到货/再次续配。重复配套不重复占书或重复扩缺册。学生领用要求本班、开放学期账户、押金余额覆盖全部在借书，且同生同学期同subject不得在跨Pack/跨版次重复领；原书归还后可再领。
5. **学生退换和损耗追踪**：issued才可退/换/报损。完好退书回available不收损耗；破损回repair，扣款≤该本押金且≤账户余额。换书必须另有兼容可用实物，排除刚还那本，保留replacement_for_id前后条码；若库存或押金不足整事务回滚，原借书继续在借。主管遗失报损改Copy lost，金额扣一次，不重复扣款。
6. **学期清算与押金退补**：Account每生每学期唯一，DepositEntry保存实收正数、损耗负数、退款负数和唯一回单号。押金实收只限open账户；期末有任何该学期issued书目就拒绝清算。全部归还/报损后，主管退款当前余额并置settled/0，不能重复退或再收款。无支付网关，退款是有凭证的本地登记。

所有修改实体的事务失败即回滚，检查库存与改变库存共用Edition父锁。全站锁5–若干Edition的范围适合小书站；不是大规模多校库存服务。MySQL READ COMMITTED使等锁后读到新提交状态，所有SUM/单本分配在同一受控区内。Account入账独立行锁，回单唯一冲突回滚余额。

## Apriori与留出评估

`backend/src/basket_rules.py`实现Apriori频繁项剪枝（最多三项），支持度≥0.15、置信度≥0.6、lift>1。96组固定seed38模拟课程篮，包含数学/物理/实验、语文/历史、数学/信息、美术/音乐等配套。先固定拆72训练/24留出，只用训练篮挖规则。留出每篮隐藏一科，剩余科为输入；命中隐藏科计召回，另记建议覆盖率与逐篮结果。这个口径是“每篮一个隐藏科的召回”，不是对真实学生需求的准确率承诺。

worker从Redis取Pack ID，查询当前课程subject及历史篮，计算真实规则，DB recommendation与共享卷`/artifacts/basket-ID.json`持久化；保存训练/留出索引、source_checksum、阈值、规则support/confidence/lift、当前建议和留出病例。失败保存failed/error，队列恢复同Pack可重试。未实现worker硬崩溃后的running自动回收。

## 一天的业务剧本

1. 08:30 核验高一3班12人，课程要求PHY-V2物理与LAB-V2实验册。馆存PHY-V2 8本、已批准兼容PHY-V1 10本，共18本物理可用；另有4本破损物理待修。LAB-V2 6本，LAB-V1 4本因缺传感器实验未批准，不能凑数。
2. 09:00 登记`REC-NEW`回收条码，先uninspected；验封面装订，有破损记repair，重新装订后再次检查usable，历史检查不丢。
3. 09:20 建`PACK-2026-G13`，两课程各12份。送worker分析72/24历史篮，查看共需与留出召回；库管确认课程单，不自动照建议采购。
4. 10:00 主管锁库存：物理12本全部配齐，实验册先锁6本，缺6本开PO。未批准LAB-V1不进入清单。
5. 10:30 PO先到3本、再到3本，逐本有PO条码；每次续配只补缺，最终24个Assignment，库存不重复扣。
6. 11:00 学生S31领物理/实验各1本；先实收4000分押金才可领。跨班学生或同生另Pack重复物理会拒，异科仍能领。
7. 14:00 物理封面轻损，换另一本兼容完好教材，前后条码留档；原书进入待修。实验册完好归还，可再次配给其他班。若物理遗失，主管损耗最多扣该书2000分，2500分会拒且不改账户。
8. 16:00 若仍有在借书，期末清算拒绝；归还或真实报损后退款余额。如4000押金减2000损耗，退款2000分，账户封存。观察席复看条码、缺册票与押金回单。

## 结构与开发

`backend/src/models.py`关系表、`schemas.py`输入校验、`common.py`库存锁/兼容查询/审计、`pack_service.py`配套与补购、`circulation_service.py`学生领退换/报损/清算、`basket_rules.py`真实Apriori、`worker.py`队列、`main.py`逐接口权限。前端六pages为catalog/inspection/packs/allocation/returns/deposits；`components/books.js`教材书脊、条码签、班级清单跨页复用；`utils/format.js`数据与转义、`utils/actions.js`请求错误恢复、store档案关联。前后端constants定义角色、Copy书况、配套/领用状态，后端规则校验、前端显示真实状态。

本地后端安装requirements并设置DATABASE_URL/REDIS_URL/JWT_SECRET，`uvicorn src.main:app --reload`与`python -m src.worker`；前端保留Compose Nginx /api代理。seed自然键只补缺，不覆盖人工检查、条码状态、兼容核定、配套、已付押金/损耗/退款；历史训练篮固定96条。测试、日志与截图在`../../test-artifacts/gb-1038/`，不混入生产源码。

局限：不接校园一卡通/支付/采购供应商；班级人数是课程份数上限，不建选课排课；押金按要求课程版次计，不按旧书折旧计；退书后不自动转配，库管需发起新配套；补购只记数量到货，不计采购款；未实现整配套取消释放、兼容映射撤销、学期账户重开或硬崩溃任务回收；课程篮为模拟数据。
