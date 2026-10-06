// Which rows the deck shows. The numbers come from results.js (demo/make_data.py) and ../dashboard/site/*.js.
window.DEMO_CONFIG = {
  title: "losslarp",
  subtitle: "Polaron track 4: which batch an SEM spot of anode comes from, and which features say so",
  team: "Luca · Adarsh · Yasith · Lente · Jude",
  repo: "github.com/LucaVendruscolo/losslarpV2",

  // answers Polaron gave for the test spots
  truth: { "3e122cbj": 2, "fn0mhxef": 1, "xrv9xvzb": 3 },
  // eval spots: the organisers marked our submission; only this one was wrong (its true batch was not given)
  evalWrong: ["soo2ax3r"],

  // held-out accuracy slide. key = a model in compare_extra.json; a key ending in "*" matches by prefix
  models: [
    { key: "V1 (label-free)", label: "V1", sub: "no labels" },
    { key: "V2 (batch-supervised)", label: "V2", sub: "batch labels, one seed" },
    { key: "V1 + V2 seed ensemble*", label: "V1 + V2", sub: "seed ensemble", final: true },
  ],

  // seed ensemble slide: single runs, then the average
  seeds: [
    { key: "V1+2 concatenated", label: "V1 + V2, seed 0" },
    { key: "V1 + v2s1 concatenated", label: "V1 + V2, seed 1" },
    { key: "V1 + v2s2 concatenated", label: "V1 + V2, seed 2" },
    { key: "V1 + v2_noseg concatenated", label: "V1 + V2, no material map" },
    { key: "V1 + V2 seed ensemble*", label: "average of the 4 runs", final: true },
  ],

  // features slide: top n harness tests by AUC; spots per side for the interval
  features: { n: 6, nB3: 17, nRest: 14 },

  timing: { sweepMs: 6000, matrixMs: 2200, contrastMs: 2600 },
};
