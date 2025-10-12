# Tenderly 交易模拟器

使用 Tenderly API 模拟以太坊交易并提取结构化数据。

---

## 快速开始

```bash
# 安装依赖
pip install web3 requests

# 重放交易
python3 main.py --tx-hash 0x交易哈希 --rpc-url https://eth.llamarpc.com

# 模拟合约调用
python3 main.py --contract 0x合约地址 --function 'balanceOf(address)' 0x地址
```

**输出：**
```
output/1/0xabc123.../
Success
```

---

## 配置

在 `config.txt` 或 `main.py` 中配置 Tenderly 凭证：
```
api_key = "YOUR_API_KEY"
account_id = "YOUR_ACCOUNT_SLUG"
project_slug = "YOUR_PROJECT_SLUG"
```

---

## 使用方法

### 方法1：重放交易

```bash
python3 main.py --tx-hash <交易哈希> --rpc-url <RPC地址>
```

**示例：**
```bash
python3 main.py --tx-hash 0xff8e9226091d513fc936ecc670030eba03f34dbe60cd012122bd18be44248d32 --rpc-url https://eth.llamarpc.com
```

### 方法2：模拟合约调用

```bash
python3 main.py --contract <地址> --function '<函数签名>' [参数...] [选项]
```

**示例：**
```bash
# 无参数
python3 main.py --contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --function 'totalSupply()'

# 带参数
python3 main.py --contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --function 'balanceOf(address)' 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0

# 指定发送者
python3 main.py --contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --function 'transfer(address,uint256)' 0xRecipient 1000000 --from 0xYourAddress

# 发送ETH
python3 main.py --contract 0xContract --function 'deposit()' --from 0xAddr --value 0xDE0B6B3A7640000

# 指定区块
python3 main.py --contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --function 'balanceOf(address)' 0xAddr --block 18000000
```

### 可选参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--from <地址>` | 发送者地址 | `0x0000...0000` |
| `--value <十六进制>` | 发送的ETH数量 | `0x0` |
| `--block <区块号>` | 模拟的区块号 | 最新区块 |

---

## 输出

所有结果保存到：`output/[链ID]/[交易哈希]/`

### 生成的文件

| 文件 | 说明 | 格式 |
|------|------|------|
| `decoded_trace.json` | Tenderly 完整模拟结果 | JSON |
| `asset_flows.csv` | 代币和 ETH 转账 | CSV |
| `call_trace.csv` | 函数调用序列 | CSV |
| `state_changes.csv` | 存储槽变化 | CSV |
| `address.txt` | 涉及的合约地址 | TXT |

### CSV 格式

**asset_flows.csv:**
```csv
token_address,name,symbol,from,to,value
0xa0b86991...,USDC,usdc,0xbbbb...,0x80bf...,10000000
```

**call_trace.csv:**
```csv
depth,from,to,call_type,function
0,0x37305...,0xa0b86...,CALL,transfer
1,0xa0b86...,0x43506...,DELEGATECALL,transfer
```

**state_changes.csv:**
```csv
Contract,Storage Slot,New Value
0x04c154b66cb340f3ae24111cc767e0184ed00cc6,0x1f,0x67ebef4c1500000000000000000000007b36768623
```
*(十六进制值自动简化：`0x000...01f` → `0x1f`)*

**address.txt:**
```
0x37305b1cd40574e4c5ce33f8e8306be057fd7341
0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
0x43506849d7c04f9138d1a2050bbf3a0c054402dd
```
*(从 `contract_ids` 提取，每行一个地址)*

### 输出格式

脚本输出两行：
```
output/[链ID]/[交易哈希]
Success
```
或
```
output/[链ID]/[交易哈希]
Failed
```

---

## 文件结构

```
simulation/
├── main.py                    # 主脚本（使用这个）
├── tenderly.py                # Tenderly API 封装
├── extract_asset_flows.py     # 资产提取（内部）
├── extract_call_trace.py      # 调用追踪提取（内部）
├── config.txt                 # API 配置
└── output/                    # 结果
    └── [链ID]/
        └── [交易哈希]/
            ├── decoded_trace.json
            ├── asset_flows.csv
            ├── call_trace.csv
            ├── state_changes.csv
            └── address.txt
```

**常见链ID：**
- `1` - 以太坊主网
- `137` - Polygon
- `56` - BSC
- `42161` - Arbitrum One
- `10` - Optimism

---

## 功能特性

- ✅ 模拟任何交易，无需上链执行
- ✅ 自动函数编码
- ✅ 提取资产转账（ERC20/ERC721/ETH）
- ✅ 提取调用追踪（过滤 JUMPDEST/STATICCALL）
- ✅ 提取存储状态变化
- ✅ 按链ID组织
- ✅ 所有CSV文件都会创建（即使为空也有列名）
- ✅ 状态变化中的十六进制值自动简化

---

## 实现细节

### 核心模块

**main.py** (307行)
- 所有操作的入口点
- 处理命令行参数
- 编排模拟和提取流程

**tenderly.py** (125行)
- `TenderlySimulator` 类：API 通信
- `get_transaction_params_by_hash()`：从区块链获取交易
- `generate_query_hash()`：缓存键生成

**extract_asset_flows.py** (155行)
- `extract_asset_changes()`：从 Tenderly 的 asset_changes 提取
- `extract_transfer_events()`：从事件日志提取
- `extract_eth_transfers()`：从 balance_diff 提取

**extract_call_trace.py** (78行)
- `extract_call_trace_recursive()`：递归追踪提取
- `extract_all_call_traces()`：主提取函数，支持过滤

### 数据提取逻辑

1. **资产流动**：合并 `asset_changes`、事件 `logs` 和 `balance_diff` 的数据
2. **调用追踪**：递归提取调用，排除 `JUMPDEST` 和 `STATICCALL`
3. **状态变化**：从 `state_diff.raw` 提取，简化十六进制值

---

## 注意事项

- 无数据时创建空CSV文件（仅包含列名）
- 简单的自定义模拟可能 `state_diff` 为 `null`（使用 `--tx-hash` 模式获取完整分析）
- 除 `main.py` 外的所有模块都是内部库 - 不要直接运行
- 结果按链ID自动组织，支持多链分析

---

## 许可证

MIT

