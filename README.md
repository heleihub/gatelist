# VPN L2TP Server List

通过 GitHub Actions 手动获取支持 L2TP/IPsec 的 VPN Gate 服务器列表。

## 使用说明

1. 点击上方 **Actions** 标签。
2. 在左侧选择 **Update L2TP Server List**。
3. 点击 **Run workflow** → 再次点击绿色按钮。
4. 等待几分钟，工作流完成后，仓库根目录会生成 `l2tp-servers.json` 和 `l2tp-servers.md`。

## 文件说明

- `l2tp-servers.json`：包含所有支持 L2TP 的服务器信息（JSON 格式）。
- `l2tp-servers.md`：Markdown 格式的表格，可直接查看。
