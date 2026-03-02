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

#### 测试接口详细设计

后端接口实现的原理为让Openclaw去执行测试命令。
Openclaw通过执行本地的shell脚本进行测试。
由于不同的测试工具，shell脚本会有所不同。
对于aiakperf测试工具，qps模式的shell脚本为：
aiakperf -m /root/DeepSeek-R1-Distill-Qwen-32B -a qianfan.baidubce.com/ -M deepseek-r1-distill-qwen-32b -H "Authorization: Bearer bce-v3/ALTAK-SnSg71JuaUo1u3OxA2YRo/6d0bd73d1c44da875f0690b221b1baf4cb4e5826" -r  qianfan_v2 -d raw_sharegpt -D /root/ShareGPT_V3_unfiltered_cleaned_split.json -n 10 -if 1024 -of 1024 -qps 3 -igr true >> aiak_test_1k_1k_2.log 2>&1 &
测试脚本需要支持传入可变参数。
在Openclaw调用本地shell脚本执行的过程中，需要把脚本的实时回显内容透出到前端界面供用户查看

#### findmaxqps函数详细设计

我的测试约束是ttft小于5，tpot小于0.05。
我将qps化为一个数值，比如是1。
调用run_aiakperf_shell后，通过extract_metrics函数解析出mean_ttft，mean_tpot。
如果mean_ttft小于ttft同时mean_tpot小于tpot则说明qps设置的小了，需要将qps调大后再调用run_aiakperf_shell测试。
如果mean_ttft大于ttft或mean_tpot大于tpot则说明qps设置大了，需要将qps调小后再调用run_aiakperf_shell测试。
通过多次迭代早到最佳的qps值。

因为find_best_qps需要调用多次才能得到结果，请在后端的回显中和前端加上对应的进度条功能

### 模型性能结果存储接口

要将模型性能的侧结果存储到数据库中，提供对应的接口将数据储存到数据库。

## 数据库

数据库使用sqlite3。
数据库中存储测试结果。

# 测试机环境初始化部分（不需要编程实现）

测试环境为一台CPU服务器，推荐配置为16C64G，硬盘空间512G，操作系统为Ubuntu 24.04

1. 测试环境需要预先安装测试工具，如安装测试工具aiakperf，aisbenchmark等
2. 需要预先下载测试集，如sharegpt数据集
3. 需要预先下载待测试模型的Tokenizer
4. 需要安装openclaw并做对应的初始化配置

后续可以做一个操作系统镜像，将测试工具，数据集都打包到镜像中