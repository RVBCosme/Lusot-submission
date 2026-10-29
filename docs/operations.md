# Operations

Run these from the repo root in Windows PowerShell 5.1, after the PATH refresh in CLAUDE.md. If the AWS login has lapsed, run `aws login --profile lusot` first. Tell the tracker before flipping any switch.

## When Meta calls pause

The analysis Lambda sets `/lusot/stop/model-calls` to `on` (C527) when:

- the Meta spend counter reaches the stop in `/lusot/spend/stop-usd`, before a run or after one
- it can't read the counter or the stop
- it can't write a run's cost to the counter

Each flip logs `spend_stop` or `spend_error`, and `SpendPauseAlarm` emails. The alarm clearing doesn't clear the switch: it stays on until someone clears it.

1. **Find why.** List the `spend_error` and `spend_stop` lines of the last hour in both log groups:

   ```powershell
   $since = [DateTimeOffset]::UtcNow.AddHours(-1).ToUnixTimeMilliseconds()
   foreach ($id in 'AnalysisLogGroup', 'ApiLogGroup') {
     $group = aws cloudformation describe-stack-resource --stack-name lusot --logical-resource-id $id --query StackResourceDetail.PhysicalResourceId --output text --profile lusot --region ap-southeast-1 --no-cli-pager
     aws logs filter-log-events --log-group-name $group --start-time $since --filter-pattern '?\"spend_error\" ?\"spend_stop\"' --query "events[].message" --output json --profile lusot --region ap-southeast-1 --no-cli-pager
   }
   ```

   The backslashes keep the pattern's double quotes through Windows PowerShell 5.1. In Git Bash, write `'?"spend_error" ?"spend_stop"'`.

   Each line names its cause:
   - `spend_stop` with `total_usd` and `stop_usd`: the stop was reached.
   - `spend_stop` with `unreadable`: the counter or the stop couldn't be read.
   - `spend_error` with `usd`: a run's cost never reached the counter.

   A `switch` inside either one means the flip itself failed, so the switch may still read `off`.

2. **Check the counter.**

   ```powershell
   uv run --directory backend/analysis --with "botocore[crt]==1.43.120" python -m lusot_analysis.spend total
   ```

   The CRT is for the `lusot` profile's `aws login` credentials. The analysis project doesn't lock it, so `--with` adds it for this run only.

3. **Add each lost amount once.** For each `spend_error` line, add its `usd` once:

   ```powershell
   uv run --directory backend/analysis --with "botocore[crt]==1.43.120" python -m lusot_analysis.spend add --usd <amount> --source manual-<who>
   ```

   Then note it in the day's log (`docs/log/YYYY-MM-DD.md`) with the line's report ID and time, so no line is added twice. The stop never moves to cover a missed amount; the amount goes on the counter instead.

4. **Clear the switch only below the stop.** Read the stop:

   ```powershell
   aws ssm get-parameter --name /lusot/spend/stop-usd --query Parameter.Value --output text --profile lusot --region ap-southeast-1 --no-cli-pager
   ```

   - If step 2's total is below it, tell the tracker and clear the switch with S6's command:

     ```powershell
     aws ssm put-parameter --name /lusot/stop/model-calls --value off --type String --overwrite --profile lusot --region ap-southeast-1 --no-cli-pager
     ```

   - At or over it, the switch stays on and the tracker asks Rene. Only `set_spend_stop.py` raises the stop, and never above 140.

5. **After any later deploy,** once the submission deploy on Nov 4 has passed, set the stop again:

   ```powershell
   uv run backend/scripts/set_spend_stop.py --usd 140
   ```

   A deploy that updates the stop's parameter puts it back to the template's 60, which only pauses spending sooner. Step 4's `get-parameter` shows the value.

## Setting the counter and the stop

- **Right after the first deploy that carries the spend stop,** seed the counter with the total the tracker sends just before that deploy:

  ```powershell
  uv run backend/scripts/seed_spend.py --usd <total>
  ```

  It seeds once and never resets the total. Exit code 3 means the counter already exists, and the script prints what it holds. If that total leaves out the tracker's, as when a run recorded its cost before the seed, add the tracker's total once with step 3's `spend add`.
- **At the submission deploy on Nov 4,** raise the stop from $60 to $140 with step 5's command. It refuses a value above 140 or below the total already spent.
