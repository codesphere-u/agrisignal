(function () {
  function showToast(msg) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    window.setTimeout(() => el.classList.remove("show"), 2200);
  }

  const navToggle = document.getElementById("nav-toggle");
  const navLinks = document.getElementById("nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      const open = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
  }

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.getAttribute("data-copy") || "";
      try {
        await navigator.clipboard.writeText(text);
        showToast("Copied to clipboard");
      } catch (err) {
        showToast("Copy failed: " + (err && err.message ? err.message : "clipboard unavailable"));
      }
    });
  });

  const cropSelect = document.getElementById("studio-crop");
  const zoneSelect = document.getElementById("studio-zone");
  const langSelect = document.getElementById("studio-lang");
  const rainInput = document.getElementById("studio-rain");
  const runBtn = document.getElementById("studio-run");

  const cropSpecs = {
    maize: { minRain: 75, maxRain: 150, optTemp: "18-28C", pest: "Fall Armyworm" },
    robusta_coffee: { minRain: 95, maxRain: 165, optTemp: "20-26C", pest: "Coffee Berry Borer & CWD" },
    beans: { minRain: 60, maxRain: 110, optTemp: "16-24C", pest: "Bean Anthracnose" },
    cassava: { minRain: 50, maxRain: 130, optTemp: "22-30C", pest: "Cassava Mosaic & Brown Streak" },
    matooke_banana: { minRain: 95, maxRain: 170, optTemp: "20-28C", pest: "Banana Bacterial Wilt" },
    groundnuts: { minRain: 55, maxRain: 115, optTemp: "21-29C", pest: "Rosette Vector Aphids" }
  };

  function updateAdvisoryStudio() {
    if (!cropSelect || !zoneSelect || !langSelect || !rainInput) return;
    const crop = cropSelect.value;
    const zone = zoneSelect.value;
    const lang = langSelect.value;
    const rain = Math.max(0, Number(rainInput.value || 95));
    const spec = cropSpecs[crop] || cropSpecs.maize;

    let status = "PLANT NOW";
    let conf = 0.88;
    if (rain < spec.minRain) {
      status = "DELAY PLANTING";
      conf = 0.74;
    } else if (rain > spec.maxRain) {
      status = "DRAINAGE GUARD";
      conf = 0.79;
    }

    const smsByLang = {
      en: `AGRISIGNAL ${crop.toUpperCase()} (${zone}): ${status}. 14d rain=${rain}mm. Watch ${spec.pest}. Scout weekly.`,
      lg: `AGRISIGNAL ${crop.toUpperCase()} (${zone}): ${status}. Enkuba 14d=${rain}mm. Kebera ${spec.pest}.`,
      sw: `AGRISIGNAL ${crop.toUpperCase()} (${zone}): ${status}. Mvua 14d=${rain}mm. Kagua ${spec.pest}.`
    };
    const sms = (smsByLang[lang] || smsByLang.en).slice(0, 160);

    const outEl = document.getElementById("studio-output");
    const smsEl = document.getElementById("studio-sms");
    if (outEl) {
      outEl.textContent = JSON.stringify({
        crop,
        agro_zone: zone,
        recommendation: status,
        point_confidence: conf,
        confidence_interval: [Number((conf - 0.08).toFixed(2)), Number(Math.min(0.99, conf + 0.06).toFixed(2))],
        data_completeness_score: 0.92,
        optimal_temp: spec.optTemp,
        ipm_watch: spec.pest
      }, null, 2);
    }
    if (smsEl) {
      smsEl.textContent = `[${sms.length}/160 chars] ${sms}`;
    }
  }

  if (runBtn) {
    runBtn.addEventListener("click", updateAdvisoryStudio);
    [cropSelect, zoneSelect, langSelect, rainInput].forEach((el) => {
      if (el) el.addEventListener("change", updateAdvisoryStudio);
    });
    updateAdvisoryStudio();
  }
})();
