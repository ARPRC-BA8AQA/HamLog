name: Bug 报告(中文)
description: 提交 Bug 报告
title: "[Bug] "
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        感谢你花时间提交 Bug 报告！请尽量详细地填写以下信息，方便我们定位和修复问题。

  - type: textarea
    id: description
    attributes:
      label: 问题描述
      description: 清晰简洁地描述你遇到的 Bug。
      placeholder: 描述 Bug 的具体表现...
    validations:
      required: true

  - type: textarea
    id: reproduce
    attributes:
      label: 复现步骤
      description: 如何一步一步复现这个问题。
      placeholder: |
        1. 打开 '...'
        2. 点击 '...'
        3. 滚动到 '...'
        4. 出现错误
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: 预期行为
      description: 你期望程序如何表现？
      placeholder: 描述正常情况下应该发生什么...
    validations:
      required: true

  - type: textarea
    id: screenshots
    attributes:
      label: 截图 / 日志
      description: 如有必要，请添加截图或日志输出以帮助说明问题。
      placeholder: 在此粘贴截图或软件日志...

  - type: input
    id: version
    attributes:
      label: 版本号
      description: 你正在使用的软件版本。
      placeholder: 例如 v1.0.0

  - type: dropdown
    id: os
    attributes:
      label: 操作系统
      description: 你正在使用的操作系统。
      options:
        - Windows 10/11
        - macOS
        - Linux
        - 其他
    validations:
      required: true

  - type: checkboxes
    id: terms
    attributes:
      label: 确认清单
      options:
        - label: 我已搜索过现有 Issue，确认这不是重复报告。
          required: true
