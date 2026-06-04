# Submitting to TACL (Transactions of the ACL): Author Guide (2025-2026)

> Verified against official sources: the TACL OJS site (transacl.org), the TACL formatting
> instructions (tacl2021v1, arXiv HTML render), the Feb-2024 TACL Appendices Policy, the ACL
> Rolling Review author guidelines/CFP, the ACL Policies wiki, and the MIT Press TACL pages.
> Every factual claim carries a source URL. Items not confirmable from an official source are
> flagged. Compiled 2026-06-04 for the CoEval paper.

---

## 1. Formatting / Style

**LaTeX template (required for final/camera-ready).** TACL provides `tacl2021v1.sty`,
`tacl2021v1-template.tex`, `acl_natbib.bst`, `tacl2021.bib`, plus the formatting-instructions
PDF; Overleaf copy linked from the submissions page
(https://transacl.org/index.php/tacl/about/submissions; Overleaf read-link
https://www.overleaf.com/read/yxyxfpfytdfn). Mirror:
https://transacl.org/tacl-submission-templates/tacl2021v1-template.tex
(https://arxiv.org/html/2405.11575v1).

**Word.** TACL distributes a `.doc` template (`tacl.doc`,
https://transacl.org/tacl-submission-templates/tacl.doc) alongside the LaTeX files, but LaTeX is
the expected format for final versions. **FLAG:** no official sentence explicitly *permits* Word
for the final camera-ready; treat **LaTeX as mandatory for the accepted version**, Word is
usable for the review submission. (https://transacl.org/index.php/tacl/about/submissions)

**Layout / font / margins (official instructions).** Two-column; **A4 (not Letter)**; Adobe
Times Roman; **body 11pt**, section titles 12pt bold, abstract 10pt, captions 10pt, footnotes
9pt; margins **2.5 cm** all sides; column width **7.7 cm**; **0.6 cm** column gap; single-spaced
(https://arxiv.org/html/2405.11575v1).

**Page limit + exclusions.** **10 content pages** for an original submission (Feb-16-2024
Appendices Policy, effective Mar-1-2024,
https://transacl.org/index.php/tacl/announcement/view/105). **References do NOT count**
(https://arxiv.org/html/2405.11575v1). **Appendices are SEPARATE from the 10 pages**, capped:
**Category 1 (replication: preprocessing, model params, proofs, pseudocode, sample
inputs/outputs INCLUDING PROMPTS, annotator guidelines, URLs) up to 5 pages; Category 2
(complementary results tables/figures) up to 3 pages**
(https://transacl.org/index.php/tacl/announcement/view/105). (The older 2021 PDF saying "7-10
pages incl. appendices" is superseded.)

**Compliance / desk-reject triggers.** "Submissions that do not comply ... risk rejection
without review." Required: confidentiality header "Confidential TACL submission. DO NOT
DISTRIBUTE."; margin line numbers; no acknowledgments in the submitted version; third-person
self-citations; remove author names from PDF metadata (https://arxiv.org/html/2405.11575v1).
ARR "Authors Beware": page-limit overflow, missing/mis-titled sections, leftover revision
meta-text, appendices not in two-column, de-anonymization (author-identifying refs, links to
non-anonymous repos) (http://aclrollingreview.org/authorchecklist).

**Anonymity: DOUBLE-BLIND.** Action Editor knows identities; reviewers do not. Fully anonymize:
no names/affiliations/identifying acknowledgments; third-person self-references; title centered
across both columns (https://transacl.org/index.php/tacl/about/submissions;
https://arxiv.org/html/2405.11575v1).

## 2. Required Sections / Content

- **Limitations.** **FLAG:** not explicitly mandated by TACL's own instructions (unlike ARR,
  where it is mandatory + page-excluded: "Papers without a limitations section will be desk
  rejected"). **Include it anyway**; budget its pages conservatively (treat exclusion as
  unconfirmed for TACL). (https://aclrollingreview.org/cfp)
- **Ethics / Responsible NLP.** Honor the ACM Code of Ethics; papers with ethical dimensions must
  discuss them; the **Responsible NLP checklist** is part of submission and a mis-filled checklist
  is a desk-reject risk (https://transacl.org/index.php/tacl/about/submissions;
  https://aclrollingreview.org/cfp).
- **Reproducibility.** Disclose (anonymized) code/data release plans in-text; Category-1 appendix
  is for replication detail (https://transacl.org/index.php/tacl/about/submissions).
- **Acknowledgements** removed from the anonymous version; added only at camera-ready.

## 3. Submission Process & System

- **Platform: TACL OJS portal at transacl.org, NOT OpenReview.** Register
  (https://transacl.org/index.php/tacl/user/register) -> submission wizard. (A common
  third-party error says OpenReview.) (https://transacl.org/index.php/tacl/about/submissions;
  https://ryokamoi.github.io/post/2024-08-24-tacl/)
- **Cadence:** one deadline on the **1st of every month, 11:59 pm Honolulu time**
  (https://transacl.org/index.php/tacl/about/submissions).
- **Complete submission:** anonymized PDF; completed Responsible NLP checklist; declaration of any
  non-anonymous preprint in "Comments to the Editor" (venue/title/URL/date); in-text code/data
  release disclosure.
- **Dual submission prohibited.** **Conference-rejection embargo:** ineligible if
  rejected/withdrawn from an *ACL venue within **9 months** of its deadline.
- **Preprints (arXiv, GitHub Pages) ARE allowed**, no anonymity period (policy explicitly covers
  TACL), provided (a) the submitted PDF is anonymized and (b) "If a non-anonymized preprint
  version exists, authors must declare its existence at submission time but should not cite it"
  (https://www.aclweb.org/adminwiki/index.php/ACL_Policies_for_Review_and_Citation;
  https://aclrollingreview.org/cfp).

## 4. Review Process & Timeline

- **Model:** Action Editor + double-blind reviewers.
- **Four outcomes:** (a) Accept; (b) **Conditional accept** (revise within **2 months**, the
  common positive outcome); (c) **Reject-and-resubmit** (within **3 months**, as a new
  submission); (d) **Reject** (12-month embargo)
  (https://transacl.org/index.php/tacl/about/submissions).
- **Time to first decision: ~2 months** (https://ryokamoi.github.io/post/2024-08-24-tacl/).
- **Revisions:** type-(b) submitted **by email** to editors ("reactivate TACL <number>"), not via
  OJS; type-(c) as a new submission number. **FLAG:** no official strict "one revision" cap or
  mandatory cover-letter format found.
- **Rebuttal:** no conference-style rebuttal phase (inferred; interaction via revision/AE channel).

## 5. After Acceptance

- **Camera-ready** from the final-version template; **no figures/tables on page 1**.
- **Presentation (optional)** at an *ACL conference (ACL/NAACL/EACL/EMNLP/AACL) if type-(a)
  accept by the conference cutoff.
- **Published by MIT Press; CC-BY license; ACL holds copyright.**
- **APC: NONE.** "TACL imposes neither author processing charges nor submission charges"
  (https://direct.mit.edu/tacl/pages/submission-guidelines).

## 6. Action checklist for CoEval (public on GitHub Pages, single-column, ~10-14pp w/ appendices)

### BIGGEST RISK: public GitHub Pages preprint vs anonymous review (allowed, with conditions)
Policy: "*ACL conferences and TACL require that submissions be anonymized." ... "If a
non-anonymized preprint version exists, authors must declare its existence at submission time
but should not cite it." (https://www.aclweb.org/adminwiki/index.php/ACL_Policies_for_Review_and_Citation)
Safe course:
1. **Keep the GitHub Pages page public** (no anonymity period).
2. **Anonymize the submitted PDF** (names, affiliations, acknowledgments, metadata).
3. **Strip links back to the named site/repo**; replace the in-paper GitHub URL with
   "[URL withheld for review]" or an anonymous mirror (anonymous.4open.science).
4. **Declare the preprint in "Comments to the Editor"** (title/URL/date), **do NOT cite/link it**.
5. **Do not over-promote** during review.

### Ordered steps to make it TACL-ready
1. **Port to the TACL template** (LaTeX `tacl2021v1` is the safe target for camera-ready; Word
   `tacl.doc` usable for the review submission). Two-column **A4, Times 11pt**.
2. **Compress main body to 10 content pages**; move prompts/worked examples/annotator guidance to
   **Category-1 appendix (<=5pp)** and complementary tables/figures to **Category-2 (<=3pp)**.
3. **Add a Limitations section** before references.
4. **Add Ethics/Broader-Impact discussion** + complete the **Responsible NLP checklist** carefully.
5. **Reproducibility statement** in-text (anonymized release plans).
6. **Anonymize:** strip names/affiliations/acks; third-person self-cites; clean PDF metadata; add
   the "Confidential TACL submission. DO NOT DISTRIBUTE." header + margin line numbers.
7. **Confirm eligibility:** not under review elsewhere; not rejected from an *ACL venue in the
   past 9 months.
8. **Register + submit on the TACL OJS portal**, target the **1st-of-month / 11:59pm Honolulu**
   deadline, and **declare the preprint** in Comments to the Editor.

## Unverified / confirm-with-editors
(a) whether Limitations is formally mandatory + page-excluded for TACL specifically; (b) whether
Word is accepted for the **final** camera-ready (LaTeX is the safe assumption); (c) exact
resubmission-bundle/cover-letter format and any hard one-revision cap; (d) that there is no
formal author rebuttal.

## Key sources
- TACL Submissions: https://transacl.org/index.php/tacl/about/submissions
- TACL Appendices Policy (Feb 2024): https://transacl.org/index.php/tacl/announcement/view/105
- TACL Formatting (arXiv render): https://arxiv.org/html/2405.11575v1
- ACL Rolling Review CFP: https://aclrollingreview.org/cfp
- ACL Policies (anonymity/preprints): https://www.aclweb.org/adminwiki/index.php/ACL_Policies_for_Review_and_Citation
- MIT Press TACL (no APC): https://direct.mit.edu/tacl/pages/submission-guidelines
- First-hand account (Kamoi 2024): https://ryokamoi.github.io/post/2024-08-24-tacl/
