---
mycelium_id: 01KDVDNA060000000000000006
title: 設計ノート
collection: core-docs
tags: [architecture, 設計]
---

# 設計ノート

イベントバスはコンポーネント間でメッセージを配送します。すべてのメッセージはスナップショット
識別子を持ちます。

## 配送保証

少なくとも一回の配送を保証します。重複は消費側で吸収してください。

## Größenordnung

Der Korpus umfasst 10²–10⁵ Dokumente. Änderungen an Überschriften ändern den Anker — das
ist beabsichtigt und wird als `ANCHOR_GONE` gemeldet.

## 术语

块（chunk）是检索单位。锚点（anchor）标识块的位置。
