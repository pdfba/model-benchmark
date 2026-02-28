# 软件功能
这是一款模型性能和精度压测软件，指定模型服务接口、测试工具、测试条件后，可以自动进行模型性能和精度压测，并生成压测报告。

# 软件架构
前端使用vue架构、后端使用python架构、数据库使用sqlite3。

## 前端
提供简单的交互界面。
### 用户需要提供如下输入
1. 待测试的模型服务地址
2. 测试工具。第一期默认为aiakperf
3. 测试条件, 输入Token长度、输出Token长度、 TTFT(ms)、TPOT(ms)
之后点击测试按钮，调用后端接口进行模型性能测试，并生成压测报告。

### 测试报告
在完成测试后，后端接口会返回测试结果，前端将测试结果展示在界面上。


## 后端
后端使用python架构。
### 模型性能测试接口
接口的输入参数为待测试的模型服务地址、测试工具、输入Token长度、输出Token长度、TTFT(ms)、TPOT(ms)。
对于aiakperf测试工具，接口的输出为文本格式如下所示
[2025-08-01 18:20:34] [perf_tool] [INFO] 1000 requests succeed, 0 requests failed
| Metric | Value |
| Perf Mode | qps 3.0 |
| Dataset | raw_sharegpt |
| Runner | openai |
| Start Time | 2025-08-01 18:14:24 |
| Total Time | 369.2649 |
| Input Tokens | 16384000 |
| Avg Input | 16384 |
| Generated Tokens | 339998 |
| Avg Output | 339 |
| Total Tokens | 16723998 |
| Num Requests | 1000 |
| Num Succeed | 1000 |
| Num Failed | 0 |
| Input Throughput | 44369.2367 |
| Generation Throughput| 920.7429 |
| Total Throughput | 45289.9796 |
| Avg Otps | 18.1365 |
| Qps | 2.7081 |
| Median Ttft | 16.6397 |
| Mean Ttft | 16.7229 |
| Std Ttft | 3.2558 |
| Percentiles Ttft | [(80.0, 20.001), (99.0, 22.962)] |
| Median Ttst | 0.6995 |
| Mean Ttst | 0.7257 |
| Std Ttst | 0.1632 |
| Percentiles Ttst | [(80.0, 0.839), (99.0, 1.209)] |
| Median Tpot | 0.0554 |
| Mean Tpot | 0.0554 |
| Std Tpot | 0.0033 |
| Percentiles Tpot | [(80.0, 0.058), (99.0, 0.062)] |
| Median E2El | 35.5161 |
| Mean E2El | 35.4869 |
| Std E2El | 3.5392 |
| Percentiles E2El | [(80.0, 38.839), (99.0, 42.333)] |
| Median Itl Smoothness| 0.0306 |
| Mean Itl Smoothness | 0.0302 |
| Std Itl Smoothness | 0.0061 |
| Percentiles Itl Smoothness | [(80.0, 0.035), (99.0, 0.043)] |
其他的测试工具的发挥内容会有所不同。

### 模型性能结果存储接口
要将模型性能的侧结果存储到数据库中，提供对应的接口将数据储存到数据库。




## 数据库
数据库使用sqlite3。
数据库中存储测试结果。