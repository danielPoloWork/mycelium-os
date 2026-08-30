# Translation status

Per-page, per-language state of the derived translations (D-028). English is canonical;
the *Page* column links to the **English source**, and the *Source commit* records which
revision of it a translation was made from.

`tools/consistency_lint.py`'s `i18n-freshness` check reads this file. It gates rows marked
`` `translated` ``: if the English source has commits after the recorded SHA, the check
fails and names the stale page. Rows marked `` `pending` `` are known gaps and are not
gated.

**Everything is `pending`.** The subsystem ships structure first (roadmap 2.13); content
work starts with the README (D-028).

Scope, layout, and the procedure for translating a page: [`README.md`](README.md).

| Page | Language | Status | Source commit |
|---|---|---|---|
| [README.md](../../README.md) | `it` | `pending` | — |
| [README.md](../../README.md) | `zh-Hans` | `pending` | — |
| [README.md](../../README.md) | `ja` | `pending` | — |
| [CONTRIBUTING.md](../../CONTRIBUTING.md) | `it` | `pending` | — |
| [CONTRIBUTING.md](../../CONTRIBUTING.md) | `zh-Hans` | `pending` | — |
| [CONTRIBUTING.md](../../CONTRIBUTING.md) | `ja` | `pending` | — |
| [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md) | `it` | `pending` | — |
| [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md) | `zh-Hans` | `pending` | — |
| [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md) | `ja` | `pending` | — |
| [SECURITY.md](../../SECURITY.md) | `it` | `pending` | — |
| [SECURITY.md](../../SECURITY.md) | `zh-Hans` | `pending` | — |
| [SECURITY.md](../../SECURITY.md) | `ja` | `pending` | — |

Translated pages live at `docs/i18n/<code>/<the same relative path>` — for example
`docs/i18n/it/README.md` for the first row. The file does not exist until the row says
`` `translated` ``.
