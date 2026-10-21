# Dataset acquisition and use guide

No external dataset is downloaded automatically. The application works offline
with the bundled synthetic CSV. Before using any third-party collection,
re-check its current terms, redistribution rules, provenance, and permitted
academic use; availability of a download is not permission to publish the data.

| Dataset/source | Access page | Fields and expected shape | License / size status | Intended use and cleanup |
|---|---|---|---|---|
| SocialPulse synthetic sample | `data/sample/socialpulse_sample.csv` in this repository | 15 generated rows; `post_id`, `text`, `timestamp`, `platform`, `brand` | Synthetic project test data; no real people, accounts, or measurements | Offline UI/API demonstrations, tests, and Hadoop smoke test only. Never present it as real public opinion. |
| TweetEval benchmark | [Official Cardiff NLP repository](https://github.com/cardiffnlp/tweeteval) | Task-specific Twitter benchmark splits; fields/format vary by task and release. Inspect the selected release's README and files before mapping text and labels. | Exact release license, access requirements, redistribution rights, and byte/row size were not independently verified for this project. Review the repository and original data terms before download or redistribution. | Candidate for labeled sentiment evaluation if its task labels and terms are suitable. Normalize task labels explicitly, preserve the official split, deduplicate carefully, and do not use unavailable tweet text for broad publication. |
| Sentiment Labelled Sentences | [UCI Machine Learning Repository dataset 331](https://archive.ics.uci.edu/dataset/331/sentiment+labelled+sentences) | Sentence text and binary sentiment label in source-specific files; verify exact columns from the downloaded release. This is review text, not necessarily social-media data. | Confirm the current UCI dataset license and current release size on its source page before reuse; neither is asserted here. | Useful only for a limited sentiment-pipeline exercise after mapping labels. Do not use it to claim social-media trend detection or platform behavior. |

## Reproducible acquisition checklist

1. Record the source page, publisher, access date, release/version, license,
   attribution, and exact file names in your report.
2. Confirm that the release allows your intended use and that any platform
   terms do not prohibit redistribution or derived outputs.
3. Store downloaded data under ignored `data/raw/`; do not commit personal data,
   credentials, or files whose redistribution is not allowed.
4. Record the text/label/date/platform column mapping and label normalization.
5. Remove empty text; report duplicate and invalid timestamp counts. Keep only
   identifiers necessary for the experiment.
6. Keep training, validation, and test splits faithful to the source; do not
   evaluate on records used to tune lexicons or model choices.
7. Document the final dataset size only after measuring the exact downloaded
   release; distinguish source-published size from the cleaned analysis count.

