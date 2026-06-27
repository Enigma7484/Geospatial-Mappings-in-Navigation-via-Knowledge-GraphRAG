# MyWay Independent Expert Review Program

## Name The Review Correctly

Feedback from invited PhDs, recent graduates, and postdocs is an **independent technical review** or **pre-submission review**. It is not formal peer review unless the paper is reviewed through a journal or conference process. LinkedIn posts and the paper should preserve that distinction.

## Review Panel

Recruit three complementary reviewers:

1. Route recommendation, learning-to-rank, or personalized navigation.
2. Trajectory reconstruction, map matching, geospatial ML, or benchmark design.
3. Recommender-systems evaluation, human preferences, or real-world experimentation.

Initial public-profile shortlist:

| Researcher | Current relevance | Best review request | Public source |
|---|---|---|---|
| Ya-Ting Yang | NYU PhD student; preference-centric and incentive-compatible route recommendation | Preference learning, feedback design, and user-compliance framing | [NYU profile](https://cyber.nyu.edu/profile/ya-ting-yang/), [2025 paper](https://arxiv.org/abs/2504.01192) |
| Valerio Ponzi | Sapienza doctoral researcher; personalized route recommendation with graph attention networks | Geolife/Porto evaluation, profile features, and route metrics | [Sapienza profile](https://phd.uniroma1.it/web/dottorato-sapienza-dottorato-nazionale-in-intelligenza-artificiale-ponzi-valerio_nP1760886.aspx), [PNMLR paper](https://doi.org/10.1109/ACCESS.2025.3555049) |
| Pablo Sanchez Perez | Early-career PhD; sequence-aware route reranking and Context Trails dataset | Reranking protocol, contextual evaluation, and public dataset strategy | [Research profile](https://pablosanchezp.github.io/pubs), [Context Trails dataset](https://zenodo.org/records/15855966) |
| Zijian Shao | Early-career recommender-systems researcher; preference-driven travel planning | Prompt/preference evaluation and constraint satisfaction | [USTC profile](https://data-science.ustc.edu.cn/_upload/tpl/15/04/5380/template5380/author/zijian-shao.html), [ACL paper](https://aclanthology.org/2025.acl-long.1339/) |

Verify each person’s current role before outreach. Do not imply endorsement from their institution.

## Review Packet

Send one link containing:

- A one-page claim sheet: contribution, evidence, and explicit non-claims.
- The current paper PDF and version/commit hash.
- A five-minute live demo or recording.
- The benchmark protocol and result files.
- Five targeted questions matched to the reviewer’s expertise.
- The feedback-use and publication-consent choices.

Keep the ask to 45 minutes. Offer co-authorship only if the person later makes a contribution that meets normal authorship standards; never offer it in exchange for favorable feedback.

## Outreach Message

```text
Subject: 45-minute technical review request: preference-aware route reranking

Hi [Name],

I am preparing MyWay, an open-data route-candidate reranking paper using OSM features and public trajectory signals. Your work on [specific paper/topic] directly overlaps with a question I am trying to answer: [one precise question].

Would you be open to a 45-minute independent technical review? I would send a one-page claim sheet, the draft, benchmark outputs, and five focused questions. I am specifically looking for criticism of the evaluation and claims, not an endorsement.

With your separate approval, I would publish a short change log crediting your feedback. You could choose attribution, an approved quote, name-only credit, or anonymity. This is a pre-submission review, not formal venue peer review.

Thank you,
[Name]
```

Personalize the first paragraph. Do not send bulk-identical messages.

## Core Review Questions

1. Is route-candidate reranking framed clearly enough against route generation and end-to-end navigation?
2. Does the Porto setup support the stated claim, and where is leakage or circularity possible?
3. Are feature-oracle and path-oracle results interpreted correctly?
4. Which external baseline is essential before submission?
5. Are the pseudo-history and personalization terms defensible?
6. Which metric would best connect offline ranking to route acceptance?
7. What claim should be removed or narrowed?
8. What single experiment would most increase publication strength?

## Review Workflow

1. Freeze a review version and record its commit hash in `docs/EXPERT_REVIEW_LOG.md`.
2. Send the same core packet to every reviewer, plus role-specific questions.
3. Record feedback faithfully, including rejected suggestions and the reason.
4. Make changes on a new version and link each change to a commit or paper section.
5. Return the summary to the reviewer for factual and quotation approval.
6. Publish only the fields covered by the reviewer’s explicit consent.
7. Submit to a formal venue if the goal is a peer-reviewed publication.

## Consent Choices

Ask each reviewer to select one:

- Public name, affiliation, feedback summary, and approved quote.
- Public name and feedback summary, no quote.
- Anonymous feedback summary.
- Private feedback only.

Silence is not consent. Save the approval date and approved wording.

## LinkedIn Change-Log Template

```text
MyWay research update: what changed after independent technical review

I asked [Reviewer, role/affiliation if approved] to challenge the evaluation of our preference-aware route reranking paper.

The strongest feedback:
- [Accurate summary]

What changed:
- [Paper/code change, with version link]

What we did not change:
- [Suggestion and transparent reason]

Current evidence:
- [One supported result]

Remaining limitation:
- [One material limitation]

This was an independent pre-submission review, not formal conference or journal peer review. Quote and attribution were approved by the reviewer.

[paper/repository/demo links]
```

The strongest post is a reproducible change log, not praise. Publish the criticism, the actual modification, and the remaining limitation together.
