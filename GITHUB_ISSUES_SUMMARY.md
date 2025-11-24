# GitHub Issues - ArXiv to reMarkable

## Summary

**Created**: 14 Phase 1 MVP issues
**Repository**: https://github.com/thomnico/arxiv-to-remarkable
**View issues**: `gh issue list --label phase-1`

## Phase 1: MVP Issues (P0)

All issues created with label `P0,phase-1` for MVP scope.

### Epic 1: Project Setup & Configuration (3 issues)

| Issue | Title | Dependencies | Estimate |
|-------|-------|--------------|----------|
| [#1](https://github.com/thomnico/arxiv-to-remarkable/issues/1) | Initialize Python Project | None | 2-3 days |
| [#2](https://github.com/thomnico/arxiv-to-remarkable/issues/2) | Environment Configuration | #1 | 1-2 days |
| [#3](https://github.com/thomnico/arxiv-to-remarkable/issues/3) | CLI Framework Setup | #1, #2 | 2-3 days |

**Total Epic 1**: ~1 week

### Epic 2: ArXiv Integration (2 issues)

| Issue | Title | Dependencies | Estimate |
|-------|-------|--------------|----------|
| [#4](https://github.com/thomnico/arxiv-to-remarkable/issues/4) | ArXiv API Client | #1, #2 | 3-4 days |
| [#5](https://github.com/thomnico/arxiv-to-remarkable/issues/5) | LaTeX Source Processor | #4 | 4-5 days |

**Total Epic 2**: ~1.5 weeks

### Epic 3: PDF Processing (2 issues)

| Issue | Title | Dependencies | Estimate |
|-------|-------|--------------|----------|
| [#6](https://github.com/thomnico/arxiv-to-remarkable/issues/6) | PDF Text Extraction | #1 | 2-3 days |
| [#7](https://github.com/thomnico/arxiv-to-remarkable/issues/7) | PDF Image Extraction | #6 | 2 days |

**Total Epic 3**: ~1 week

### Epic 4: Image Optimization (2 issues)

| Issue | Title | Dependencies | Estimate |
|-------|-------|--------------|----------|
| [#8](https://github.com/thomnico/arxiv-to-remarkable/issues/8) | Image Resizer for reMarkable 1 | #1 | 2 days |
| [#9](https://github.com/thomnico/arxiv-to-remarkable/issues/9) | E-ink Optimization | #8 | 2-3 days |

**Total Epic 4**: ~1 week

### Epic 5: EPUB Generation (4 issues)

| Issue | Title | Dependencies | Estimate |
|-------|-------|--------------|----------|
| [#10](https://github.com/thomnico/arxiv-to-remarkable/issues/10) | EPUB Structure Builder | #1 | 3 days |
| [#11](https://github.com/thomnico/arxiv-to-remarkable/issues/11) | HTML Content Generation | #10 | 3-4 days |
| [#12](https://github.com/thomnico/arxiv-to-remarkable/issues/12) | CSS Styling | #11 | 2-3 days |
| [#13](https://github.com/thomnico/arxiv-to-remarkable/issues/13) | EPUB Assembly & Validation | #12 | 3 days |

**Total Epic 5**: ~2 weeks

### Epic 6: reMarkable Integration (1 issue)

| Issue | Title | Dependencies | Estimate |
|-------|-------|--------------|----------|
| [#14](https://github.com/thomnico/arxiv-to-remarkable/issues/14) | rmapi Integration | #13 | 2-3 days |

**Total Epic 6**: ~3 days

## Phase 1 Critical Path

```
#1 (Setup)
  → #2 (Config)
    → #3 (CLI)
    → #4 (ArXiv Client)
      → #5 (LaTeX Processor)
    → #6 (PDF Extract)
      → #7 (PDF Images)
  → #8 (Image Resize)
    → #9 (E-ink Optimize)
  → #10 (EPUB Structure)
    → #11 (HTML Gen)
      → #12 (CSS)
        → #13 (EPUB Assembly)
          → #14 (reMarkable Upload)
```

**Critical Path Duration**: ~6 weeks

## Dependency Matrix

| Issue | Blocks |
|-------|--------|
| #1 | #2, #4, #6, #8, #10 |
| #2 | #3, #4 |
| #3 | (CLI ready for integration) |
| #4 | #5 |
| #5 | (LaTeX processing complete) |
| #6 | #7 |
| #7 | (PDF processing complete) |
| #8 | #9 |
| #9 | (Images ready for EPUB) |
| #10 | #11 |
| #11 | #12 |
| #12 | #13 |
| #13 | #14 |
| #14 | (MVP complete!) |

## Parallel Work Opportunities

Can be worked on simultaneously:
- **Epic 1** (Setup) - Week 1
- **Epic 2** (ArXiv) + **Epic 3** (PDF) - Weeks 2-3 (parallel)
- **Epic 4** (Images) - Week 3 (parallel with Epic 3)
- **Epic 5** (EPUB) - Weeks 4-5
- **Epic 6** (Upload) - Week 6

## Next Steps

### To start work:
```bash
# View all Phase 1 issues
gh issue list --label phase-1

# Start with issue #1
gh issue view 1

# Self-assign when starting
gh issue edit 1 --add-assignee @me

# Create branch
git checkout -b feature/1-1-python-project-setup
```

### To track progress:
```bash
# List open Phase 1 issues
gh issue list --label phase-1 --state open

# Create project board (recommended)
gh project create --title "ArXiv to reMarkable MVP" \
  --body "Phase 1: Core EPUB conversion pipeline"
```

## Future Phases

**Phase 2 issues** (to be created later):
- [7.x] Groq Vision OCR integration
- [8.x] Batch processing
- [9.x] User configuration

**Phase 3 issues** (to be created later):
- [10.x] Testing & quality assurance
- [11.x] Documentation
- [12.x] Distribution (PyPI, Docker, CI/CD)

## Labels Used

- `P0` - Must-have for MVP launch (red)
- `P1` - Important for Phase 2 (yellow)
- `P2` - Nice-to-have, future (green)
- `phase-1` - Phase 1: MVP (blue)
- `phase-2` - Phase 2: Advanced (purple)
- `phase-3` - Phase 3: Polish (dark blue)

## Resources

- **PRD**: See `PRD.md`
- **Task Breakdown**: See `TASKS.md`
- **Groq OCR Reference**: See `docs/GROQ_OCR_INTEGRATION.md`
- **CLAUDE.md**: See `.claude/CLAUDE.md`

---

**Created**: 2025-11-24
**Total Phase 1 Issues**: 14
**Estimated Duration**: 6 weeks
