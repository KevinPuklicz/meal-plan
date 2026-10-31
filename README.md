# meal-plan

Weekly gluten-free dinner plan for No Frills Waterloo, with price-match proofs.

- **Latest week:** https://kevinpuklicz.github.io/meal-plan/
- Past weeks live in `weeks/<week>/`.
- Built every Friday by a Claude scheduled task: `tools/flyerkit.py` pulls Flipp flyer data and renders a boxed crop of each price-matched item; `tools/build_site.py` turns `tools/plan_<week>.json` into the page.
