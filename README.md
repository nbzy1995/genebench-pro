---
license: mit
pretty_name: GeneBench-Pro
language:
- en
tags:
- biology
- genomics
- benchmark
- reasoning
- agents
- case-study
- synthetic-data
- tabular
configs:
- config_name: problems
  data_files:
  - split: release
    path: problems.csv
---

# GeneBench-Pro Public Case Studies

This repository contains public GeneBench-Pro case studies. It is the
self-contained package intended for public distribution, including Hugging Face
publication.

## Package Layout

```text
<repo-root>/
├── .gitattributes
├── README.md
├── LICENSE
├── problems.csv
├── checksums.sha256
├── manifest.json
├── reference_definitions.md
├── reference_grader.py
└── problems/
    └── <eval_id>/
        ├── eval_config.json
        ├── data_files/
        └── report_public.pdf
```

Each problem directory contains only the release-facing assets:

- `eval_config.json`: the public task, data-file list, answer schema, ground
  truth, grader contract, and eval UUID.
- `data_files/`: the staged files visible to an agent for that problem.
- `report_public.pdf`: the public scientific case-study report.

Use each problem's `eval_config.json` for the task, answer schema, reference
values, and grading contract.

The ground-truth answers and grader tolerances are intentionally public. This
package is for public case studies, reproducibility, and model-analysis
examples, not for a hidden-answer leaderboard.

The staged records are released as problem-local benchmark files. The task
prompts use the provenance statement: `Data provenance is uncertain; use your
best scientific judgement`.

`problems.csv` provides a Hugging Face-friendly one-row-per-problem summary
table and primary package inventory. `manifest.json` includes per-problem file
paths, SHA-256 checksums, and file sizes; `checksums.sha256` provides
package-wide integrity information in a standard flat-file format.

## Problems

| Order | Eval ID | Public title | Domain |
|---:|---|---|---|
| 0 | `multiparent_qtl_hmm_lmm` | Multi-parent QTL mapping with founder reconstruction | Statistical genetics |
| 1 | `statgen_cis_mvmr_winnerscurse_scaling_ldaware` | LD-aware cis-MVMR with winner's-curse correction | Proteomics / statistical genetics |
| 2 | `txr1_mtb_causal_sv` | Synthetic structural-variant driven tumor therapy decision | Cancer somatic / clinical genomics |
| 3 | `structural_inversion_subhap_expression_risk` | Structural inversion subhaplotype expression and disease risk | Clinical genomics |
| 4 | `wf_selection` | Wright-Fisher selection inference from allele-frequency trajectories | Population genetics |
| 5 | `hic_sv_masked_loop_strength` | Masked Hi-C loop strength under structural variation | 3D genomics / structural variation |
| 6 | `statgen_scrna_ambient_state_eqtl` | Ambient RNA and cell-state-aware eQTL mapping | Single-cell statistical genetics |
| 7 | `carrier_cnv_pseudogene_residual_risk` | DRX1 carrier-screening residual risk under CNV and pseudogene calibration | Clinical genomics / carrier screening |
| 8 | `crispri_casrx_transcript_vs_locus` | Transcript-vs-locus CRISPRi decision with CasRx follow-up | Functional genomics |
| 9 | `popgen_recent_pulse_sexbias` | Recent sex-biased admixture pulse inference | Population genetics |

The titles in this table are broad showcase titles for the package inventory. The
PDF reports use more technical case-study titles on their first pages.

## Running a Problem

To run a case study, keep one problem directory intact or copy its
`eval_config.json` together with the files listed in `data_files/`, preserving
those relative paths or updating them in the config. A runner should read
`eval_config.json`, show the agent the `task` text, make only the staged
`data_files/` available in the analysis workspace, collect an
`eval_answer.json`, and then grade it with the public grader contract. The
config anatomy is:
`id` and `eval_uuid` identify the problem instance; `task` describes the run;
`data_files` lists the visible inputs;
`ground_truth` contains the released reference answer; and `grader` specifies
the field-level grading rules and tolerances. In an operational hidden-answer
evaluation, only the task text and staged data files would be made available
during the run, while `ground_truth` and `grader` would stay on the runner side.
They are included here because this package is a public case-study and
reproducibility release.

## Using the Grader Contract

An answer should be a JSON object shaped like:

```json
{
  "answer": {
    "<field_name>": "<value>"
  },
  "reasoning": "<brief method description>"
}
```

The exact answer fields are problem-specific and are listed in each
`eval_config.json` under `ground_truth` and `grader.config`.

To check an answer with the included reference implementation:

```bash
python3 reference_grader.py \
  problems/multiparent_qtl_hmm_lmm/eval_config.json \
  path/to/eval_answer.json
```

The reference grader requires Python 3.10 or newer. The boolean `passed` field
is the authoritative grading decision; `score` is a diagnostic summary of
graded fields and should not be used as a substitute for `passed`.

See `reference_definitions.md` for the grader-field definitions and scoring
semantics.

## License

This public package is available under the MIT License.
