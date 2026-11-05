# Who funds the 2026 House races?

*An analysis of large-donor, PAC, and other money in US House campaigns.*

**Incumbents in both parties lean on PACs far more than challengers or open-seat candidates: PACs supplied 27% of funding for Democratic imcumbents and 30% of funding for Republican incumbents, versus 5%-7% for challengers and open-seat candidates.**

## What I found
1. **PAC money follows incumbency, not party.** PACs gave 27% pf Democratic and 30% of Republican incumbents' receipts, compared with 5% for Democrat challengers and 6% for Republican challengers. The ten candidates most reliant on PACs (70% to 80% of receipts) are all incumbents.
2. **Democratic challengers and open-seat candidates were mostly funded by large individual donors** (52% and 57% of receipts), compared with 30% and 32% for their Republican counterparts. Republican challengers and open-seat candidates drew most of their funding (64% and 61%) from the "everything else" category, which can't be accurately broken down further (see limitations).
3. **Democrats filled 8 of the 10 biggest fundraising totals**, led by Alexandria Ocasio-Cortez ($38.0M). Four of these eight were incumbents, including David Trone ($26.2M)

## Method
- Data: Find candidate-level fundraising totals for the 2026 election cycle from the Federal Election Commission's openFEC API, pulled on 11/3/2026. Filings cover reporting periods through 11/03/2026.
- Sample: 1320 House candidates who raised at least $100,000.
- Large donors: Itemized individual contributions (donors who gave more than $200 in total over the cycle).
- PACs: Contributions made from other political committees.
- "Everything else": Total receipts minus the two groups above. This includes small donors, party transfers, loans, and candidate self-funding.
- Shares: Calculated as dollars from each source divided by total receipts, summed across candidates in each group (dollar-weighted). 

## Limitations
- "Everything else" can't separate small donors from loans, party transfers, and self funding, so I can't treat it as a small donor figure .
- Totals are snapshots of the latest filings and will change.
- Campaign money isn't the same as outside spending by super PACs, which isn't included.

## Reproduce it
```bash
pip install requests pandas matplotlib
export FEC_API_KEY=yor_key
python main_file.py
```

## About
Built by Aleyah Sidhu ([LinkedIn](linkedin.com/in/aleyah-sidhu)) with Python (pandas, matplotlib) and the openFEC API.
