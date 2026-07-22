window.drawCharts = function () {
  var styles = getComputedStyle(document.documentElement);
  var chart = Plot.plot({
    width: 620,
    height: 240,
    marginLeft: 70,
    style: { background: "transparent", fontSize: "12px" },
    x: { label: "Findings", grid: true },
    y: { label: null, domain: ["Critical", "High", "Medium", "Low"] },
    marks: [
      Plot.barX([
        { sev: "Critical", n: 2 },
        { sev: "High", n: 37 },
        { sev: "Medium", n: 65 },
        { sev: "Low", n: 10 }
      ], { x: "n", y: "sev", fill: styles.getPropertyValue("--accent").trim() }),
      Plot.ruleX([0])
    ]
  });
  document.getElementById("viz-vuln").appendChild(chart);
};
