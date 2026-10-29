# Operations

Run these from the repo root in Windows PowerShell 5.1, after the PATH refresh in CLAUDE.md. If the AWS login has lapsed, run `aws login --profile lusot` first. Tell the tracker before flipping any switch.

## When Meta calls pause

The analysis Lambda sets `/lusot/stop/model-calls` to `on` (C527) when:

- the Meta spend counter reaches the stop in `/lusot/spend/stop-usd`, before a run or after one
- it can't read the counter or the stop
- the counter isn't seeded yet, as in a new or re-created limits table
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
   - `spend_stop` with `unseeded`: the counter has no seed yet, so it is never read as $0. Seed it as "Setting the counter and the stop" says.
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

   Compare it with the latest total: step 3's last output, or step 2's if nothing was added.

   For a `spend_stop` whose cause is `unreadable`, such as a missing `/lusot/spend/stop-usd` or a denied read, fix the named error before clearing, or the next photo pauses again. For `unseeded`, seed the counter first.

   - If the latest total is below the stop, tell the tracker and clear the switch with S6's command:

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

Only a seeded counter is read. Until the seed, the counter reads as `unseeded`, never as $0, so a photo pauses model calls, and `spend total` and `set_spend_stop.py` print `unseeded` and exit 1.

- **The first deploy that carries the spend stop** goes in this order:
  1. The stack check (Task 15 Step 2a): a read-only `get-template` of `lusot`, whose logical ids must all be in `backend/template.yaml`. If one isn't, stop and tell the tracker which; delete nothing.
  2. The deploy.
  3. Seed the counter with the total the tracker sends just before that deploy:

     ```powershell
     uv run backend/scripts/seed_spend.py --usd <total>
     ```

     It adds that total once and prints the new total. A run that recorded its cost before the seed is kept: the seed adds to it. A second seed exits 1 with `already seeded` and writes nothing; a missed amount goes in with `spend add` instead (step 3 of "When Meta calls pause").
  4. If a photo between the deploy and the seed flipped `/lusot/stop/model-calls`, clear it as step 4 of "When Meta calls pause" says.
- **After a deploy that removed or replaced `LimitsTable`,** as when a template without it is deployed to `lusot`: the template's `DeletionPolicy` and `UpdateReplacePolicy` keep the old table, outside the stack, with its old name and its counter. The stack's new table starts unseeded, so model calls pause with `unseeded`.
  1. Find the old table: the limits table that isn't the stack's own.

     ```powershell
     aws dynamodb list-tables --query "TableNames[?contains(@, 'LimitsTable')]" --output text --profile lusot --region ap-southeast-1 --no-cli-pager
     aws cloudformation describe-stack-resource --stack-name lusot --logical-resource-id LimitsTable --query StackResourceDetail.PhysicalResourceId --output text --profile lusot --region ap-southeast-1 --no-cli-pager
     ```

  2. Read its counter, read-only. The answer is in micro-dollars: divide it by 1,000,000 for USD.

     ```powershell
     aws dynamodb get-item --table-name <old table> --key '{\"pk\":{\"S\":\"spend#meta\"}}' --consistent-read --query Item.micro_usd.N --output text --profile lusot --region ap-southeast-1 --no-cli-pager
     ```

     The backslashes keep the key's double quotes through Windows PowerShell 5.1. In Git Bash, write `'{"pk":{"S":"spend#meta"}}'`.
  3. Seed the new table with that total plus anything logged since: each `spend_error` amount from after the old table left the stack that the day's log doesn't show as added. Whatever a run or `spend add` already wrote to the new table stays, and the seed adds to it.

     ```powershell
     uv run backend/scripts/seed_spend.py --usd <total>
     ```

  4. Clear the switch as step 4 of "When Meta calls pause" says, and note the old table's name in the day's log. Leave the old table for Rene to delete.
- **At the submission deploy on Nov 4,** raise the stop from $60 to $140 with step 5's command. It refuses a value above 140 or below the total already spent.
