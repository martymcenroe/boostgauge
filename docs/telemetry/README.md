# Factory telemetry

Each dated folder holds the AssemblyZero factory's DynamoDB telemetry about boostgauge's runs, exported from the table `assemblyzero-telemetry`. The table deletes every event 90 days after it is written, so these files are the lasting record. The `.jsonl` file has one event per line, exactly as DynamoDB returned it; `manifest.json` gives the export time, the match rule, the counts, the date range and the file's sha256.
