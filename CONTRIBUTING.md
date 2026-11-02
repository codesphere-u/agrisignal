# Contributing to AgriSignal

Thank you for helping build resilient, offline-first decision support tools for smallholder farmers and extension workers!

## Development Workflow

1. Clone the repository and run the test suite:
   ```bash
   uv run --with pytest --with fastapi --with httpx --with pydantic pytest -v
   ```
2. Ensure any new crop profiles or agro-ecological rules in `agrisignal/advisory/` include:
   - Deterministic `rule_trace` entries explaining why the rule fired.
   - Accurate uncertainty propagation when optional sensors (`soil_ph`, `soil_moisture_index`, `temp_anomaly_c`) are absent.
   - Translations in English (`en`), Luganda (`lg`), and Swahili (`sw`) whose SMS representations remain `<= 160` characters.
3. Add unit and integration tests in `tests/` for all new functionality.
