# Overnight poker evaluation, 7 November 2026

The final recommendation was to keep defaults. The locked finalist gained +14.71 bb/100 in the held-out test, with a 95% confidence interval of +12.34 to +17.07. Its regressions against the combined default and MainBot exceeded the preset limit.

- [Final morning report](MORNING_REPORT.md)
- [Full statistics](statistics.json), [tested configurations](configurations.json), and [recommendation](recommendation.json)
- [Sealed experiment plan](plan.json) and [frozen arena rules](rules.md)
- [GitHub release with the complete archive, match CSV, paired comparison CSV, and SHA-256 checksums](https://github.com/lembzg/guh-poker/releases/tag/overnight-final-2026-11-07)

The archive contains the SQLite database, raw hand histories, logs, packed variants, and frozen source snapshots. Verify the downloaded archive with the published checksums and extract it with:

```sh
sha256sum --ignore-missing -c SHA256SUMS.txt
tar --zstd -xf guh-poker-overnight-final-2026-11-07.tar.zst
```
