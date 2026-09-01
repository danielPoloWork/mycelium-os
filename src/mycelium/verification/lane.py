# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""`mycelium verify`, end to end: read the tree, measure, stamp, maybe promote.

The lane reads tier 2 and writes tier 2, and touches nothing else. No store, no
snapshot, no index — a verification changes what a document *claims about itself*,
and the compiler learns about it on the next build like any other edit (D-021).

**What gets verified.** Documents whose provenance says `origin: synthesized`,
wherever they sit. That is narrower than "everything under `candidate/`" and
wider than it too, on purpose: a hand-authored note in `verified/` has no
citations to check and would score a meaningless 1.0, while a *promoted* synthetic
document is exactly the one worth re-checking — its evidence has had time to move
underneath it. Gate G7's own words are about a synthesized doc (spec 04 §7.3).

**Stamping is conditional, and the date means something.** The block is rewritten
only when the score or the checker changed. `verified_at` therefore records when
the grounding last *moved*, not when it was last looked at — which is the useful
reading, and it keeps a nightly `verify` from producing a daily diff and a daily
rebuild of a corpus nothing happened to.

**The three fields travel together.** The compiler ignores a partial verification
block and warns (spec 03 §3), so writing `grounding` without the other two would
put a warning on every candidate in the corpus. All three are written by this
lane; spec 05 §2's table assigns `verified_at` to `promote` alone, and that
assignment cannot be honoured without generating that warning — the deviation and
its reason are ADR-0036's.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from mycelium.__about__ import __version__
from mycelium.corpus import CorpusScope
from mycelium.markdown.adapter import MarkdownError, parse_markdown
from mycelium.markdown.frontmatter import Frontmatter, FrontmatterError, parse_frontmatter
from mycelium.sdk.protocols import EvidenceDocument
from mycelium.sdk.types import KirDocument, ProvenanceOrigin
from mycelium.synthesis.candidate import CANDIDATE_DIRNAME
from mycelium.synthesis.lane import evidence_of
from mycelium.verification.entailment import DEFAULT_SAMPLE_SIZE, EntailmentJudge
from mycelium.verification.errors import UnmeasurableError
from mycelium.verification.grounding import Blocker, Grounding, Thresholds, measure
from mycelium.verification.promotion import VERIFIED_DIRNAME, Moved, promote, stamp

__all__ = [
    "EVIDENCE_DIRNAME",
    "Subject",
    "Verified",
    "checker_identity",
    "evidence_set",
    "subjects",
    "verify_document",
    "verify_tree",
]

EVIDENCE_DIRNAME = "evidence"
"""Under `knowledge/`: where the deterministic lane's projections live (ADR-0034)."""


@dataclass(frozen=True, slots=True)
class Subject:
    """One document under verification, as read from the tree."""

    path: PurePosixPath
    """Repository-relative, POSIX — the form frontmatter and citations use."""

    text: str
    kir: KirDocument
    frontmatter: Frontmatter

    @property
    def status_folder(self) -> str | None:
        for part in self.path.parts:
            if part in {CANDIDATE_DIRNAME, VERIFIED_DIRNAME}:
                return part
        return None


@dataclass(frozen=True, slots=True)
class Verified:
    """What verifying one document did."""

    grounding: Grounding
    blockers: tuple[Blocker, ...]
    stamped: bool
    """Whether the document's verification block was rewritten."""

    checker: str = ""
    """What vouched, in the form `verified_by` records — computed once, here, so a
    caller that promotes on the strength of this measurement stamps the identity of
    the check that was actually run."""

    promoted: Moved | None = None

    def as_dict(self) -> dict[str, object]:
        payload = self.grounding.as_dict()
        payload["checker"] = self.checker
        payload["blockers"] = [item.as_dict() for item in self.blockers]
        payload["passes"] = not self.blockers
        payload["stamped"] = self.stamped
        payload["promoted"] = None if self.promoted is None else self.promoted.as_dict()
        return payload


def checker_identity(judge: EntailmentJudge | None, *, self_judged: bool = False) -> str:
    """What to record in `verified_by` when the gate is what vouched.

    Names the components that were actually measured and the model that judged, so
    a reader of the file — or of a diff, six months later — can tell a fully
    checked document from one whose entailment nobody could measure.
    """
    if judge is None:
        return f"mycelium verify {__version__} (coverage only)"
    suffix = "; self-judged" if self_judged else ""
    return f"mycelium verify {__version__} (coverage + entailment via {judge.identity}{suffix})"


def _documents(root: Path, scope: CorpusScope) -> Iterator[tuple[PurePosixPath, str]]:
    base = scope.scope_of(root)
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*.md")):
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if scope.contains(relative, authored_tree=scope.has_authored_tree(root)):
            yield relative, path.read_text(encoding="utf-8")


def evidence_set(root: Path, scope: CorpusScope) -> tuple[EvidenceDocument, ...]:
    """Every projected evidence document, parsed as a citation target.

    Read through the same helper the synthesis lane uses, so a citation that
    resolved when the document was written is resolved the same way now. A
    disagreement between the two would make every drift report suspect.
    """
    found: list[EvidenceDocument] = []
    for relative, text in _documents(root, scope):
        if EVIDENCE_DIRNAME not in relative.parts:
            continue
        try:
            found.append(evidence_of(relative, text))
        except (MarkdownError, FrontmatterError) as error:
            msg = f"{relative.as_posix()} cannot be read as evidence: {error}"
            raise UnmeasurableError(msg) from error
    return tuple(found)


def subjects(root: Path, scope: CorpusScope) -> tuple[Subject, ...]:
    """Every synthesized document in the tree, in path order."""
    found: list[Subject] = []
    for relative, text in _documents(root, scope):
        if EVIDENCE_DIRNAME in relative.parts:
            continue
        try:
            parsed = parse_frontmatter(text)
        except FrontmatterError:
            continue
        if parsed.frontmatter.origin is not ProvenanceOrigin.SYNTHESIZED:
            continue
        try:
            compiled = parse_markdown(text)
        except (MarkdownError, FrontmatterError) as error:
            msg = f"{relative.as_posix()} cannot be parsed: {error}"
            raise UnmeasurableError(msg) from error
        found.append(
            Subject(
                path=relative,
                text=text,
                kir=compiled.kir,
                frontmatter=compiled.frontmatter,
            )
        )
    return tuple(found)


def verify_document(
    root: Path,
    subject: Subject,
    evidence: Sequence[EvidenceDocument],
    *,
    thresholds: Thresholds,
    judge: EntailmentJudge | None = None,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    self_judged: bool = False,
    today: date | None = None,
    write: bool = True,
    auto_promote: bool = False,
) -> Verified:
    """Measure one document, stamp what changed, and promote it if allowed to."""
    grounding = measure(
        subject.path,
        subject.kir,
        evidence,
        judge=judge,
        sample_size=sample_size,
        self_judged=self_judged,
    )
    blockers = grounding.blockers(thresholds)
    identity = checker_identity(judge, self_judged=self_judged)
    when = today or date.today()

    stamped = False
    if write and _moved(subject.frontmatter, grounding.score, identity):
        text = stamp(
            subject.text,
            verified_by=identity,
            verified_at=when,
            grounding=grounding.score,
        )
        (root / subject.path).write_text(text, encoding="utf-8", newline="")
        stamped = True

    promoted = None
    if auto_promote and not blockers and subject.status_folder == CANDIDATE_DIRNAME:
        promoted = promote(
            root,
            subject.path,
            verified_by=identity,
            grounding=grounding.score,
            at=when,
        )
    return Verified(
        grounding=grounding,
        blockers=blockers,
        stamped=stamped,
        checker=identity,
        promoted=promoted,
    )


def _moved(frontmatter: Frontmatter, score: float, identity: str) -> bool:
    """Whether the recorded verification block is out of date.

    Compared at the precision the file carries (four decimals), so a judge whose
    sample happens to land the same way twice does not produce a diff — and a real
    change of one hundredth of a point does.
    """
    recorded = frontmatter.grounding
    if recorded is None or frontmatter.verified_by != identity:
        return True
    return round(recorded, 4) != round(score, 4)


def verify_tree(
    root: Path,
    scope: CorpusScope,
    *,
    thresholds: Thresholds,
    judge: EntailmentJudge | None = None,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    self_judged: bool = False,
    only: Sequence[PurePosixPath] = (),
    today: date | None = None,
    write: bool = True,
    auto_promote: bool = False,
) -> tuple[Verified, ...]:
    """Verify every synthesized document, or just the ones `only` names."""
    evidence = evidence_set(root, scope)
    wanted = {path.as_posix() for path in only}
    results: list[Verified] = []
    for subject in subjects(root, scope):
        if wanted and subject.path.as_posix() not in wanted:
            continue
        results.append(
            verify_document(
                root,
                subject,
                evidence,
                thresholds=thresholds,
                judge=judge,
                sample_size=sample_size,
                self_judged=self_judged,
                today=today,
                write=write,
                auto_promote=auto_promote,
            )
        )
    return tuple(results)
