# Known Limitations & Biosafety Boundaries

1. **No Yield Guarantees**:
   - AgriSignal evaluates agro-climatic and edaphic preconditions using transparent rule-based heuristics. It does **not** predict harvest tonnage or financial returns. Micro-topography (valley bottoms vs. hillslopes), seed germination rates, and weeding timeliness must be assessed on-plot.
2. **Non-Chemical IPM Only**:
   - To prevent ecological harm, pollinator loss, and smallholder chemical poisoning, AgriSignal never prescribes synthetic insecticides or fungicides. When pest risk reaches `HIGH` or `SEVERE`, farmers and community agents are directed to escalate to a certified District Agricultural Extension Officer.
3. **Zonal Generalization**:
   - The 4 built-in agro-ecological zones represent regional East African baselines. Plots situated in localized rain shadows or high-altitude microclimates (>2,200m ASL) should supply direct `soil_moisture_index` and `temp_anomaly_c` measurements to narrow uncertainty bounds.
