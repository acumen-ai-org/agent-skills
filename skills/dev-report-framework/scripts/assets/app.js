(function () {
  "use strict";

  var embedded = {};
  var island = document.getElementById("report-data");
  if (island && island.textContent.trim()) {
    try {
      embedded = JSON.parse(island.textContent);
    } catch (error) {
      embedded = {};
    }
  }
  window.__REPORT_DATA__ = embedded;

  var fetchCache = {};

  function getData(path) {
    if (Object.prototype.hasOwnProperty.call(window.__REPORT_DATA__, path)) {
      return Promise.resolve(window.__REPORT_DATA__[path]);
    }
    if (fetchCache[path]) {
      return fetchCache[path];
    }
    fetchCache[path] = fetch(path).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status + " for " + path);
      }
      return response.json();
    });
    return fetchCache[path];
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "class") {
          node.className = attrs[key];
        } else if (key === "text") {
          node.textContent = attrs[key];
        } else {
          node.setAttribute(key, attrs[key]);
        }
      });
    }
    (children || []).forEach(function (child) {
      if (typeof child === "string") {
        node.appendChild(document.createTextNode(child));
      } else if (child) {
        node.appendChild(child);
      }
    });
    return node;
  }

  function clear(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  var state = {
    manifest: null,
    releases: [],
    splitMode: false,
    currentPath: null,
    currentCategory: null,
    currentId: null,
    previousIndex: 0
  };

  function renderMarkdown(section) {
    var wrap = el("div", { class: "md-body" });
    var raw = window.marked ? window.marked.parse(section.md || "") : section.md || "";
    wrap.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(raw) : "";
    return wrap;
  }

  function renderTable(section) {
    var wrap = el("div");
    var columns = section.columns || [];
    var rows = (section.rows || []).slice();
    var sortKey = section.defaultSort ? section.defaultSort.key : null;
    var sortDir = section.defaultSort ? section.defaultSort.dir : "asc";
    var filterText = "";

    function build() {
      clear(wrap);
      if (section.filterable) {
        var input = el("input", {
          class: "table-filter",
          type: "text",
          placeholder: "Filter rows…"
        });
        input.value = filterText;
        input.addEventListener("input", function () {
          filterText = input.value.toLowerCase();
          build();
          input.focus();
          input.setSelectionRange(input.value.length, input.value.length);
        });
        wrap.appendChild(input);
      }

      var table = el("table", { class: "data" });
      var headRow = el("tr");
      columns.forEach(function (column) {
        var th = el("th", { text: column.label });
        if (column.sortable) {
          if (column.key === sortKey) {
            th.textContent = column.label + (sortDir === "asc" ? " ▲" : " ▼");
          }
          th.addEventListener("click", function () {
            if (sortKey === column.key) {
              sortDir = sortDir === "asc" ? "desc" : "asc";
            } else {
              sortKey = column.key;
              sortDir = "asc";
            }
            build();
          });
        }
        headRow.appendChild(th);
      });
      table.appendChild(el("thead", null, [headRow]));

      var visible = rows.filter(function (row) {
        if (!filterText) {
          return true;
        }
        return columns.some(function (column) {
          return String(row[column.key] == null ? "" : row[column.key])
            .toLowerCase()
            .indexOf(filterText) !== -1;
        });
      });

      if (sortKey) {
        var sortColumn = columns.filter(function (column) {
          return column.key === sortKey;
        })[0];
        var numeric = sortColumn && sortColumn.type === "number";
        visible.sort(function (a, b) {
          var av = a[sortKey];
          var bv = b[sortKey];
          var result;
          if (numeric) {
            result = (Number(av) || 0) - (Number(bv) || 0);
          } else {
            result = String(av == null ? "" : av).localeCompare(
              String(bv == null ? "" : bv)
            );
          }
          return sortDir === "asc" ? result : -result;
        });
      }

      var tbody = el("tbody");
      visible.forEach(function (row) {
        var tr = el("tr");
        columns.forEach(function (column) {
          var value = row[column.key];
          tr.appendChild(el("td", { text: value == null ? "" : String(value) }));
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      wrap.appendChild(table);
    }

    build();
    return wrap;
  }

  function renderKeyValue(section) {
    var dl = el("dl", { class: "kv" });
    (section.pairs || []).forEach(function (pair) {
      dl.appendChild(el("dt", { text: String(pair.k) }));
      dl.appendChild(el("dd", { text: String(pair.v) }));
    });
    return dl;
  }

  function renderMetricCards(section, deltas) {
    var wrap = el("div", { class: "cards" });
    (section.cards || []).forEach(function (card) {
      var valueText = String(card.value);
      if (card.unit) {
        valueText += " " + card.unit;
      }
      var pieces = [
        el("div", { class: "card-value", text: valueText }),
        el("div", { class: "card-label", text: card.label })
      ];
      if (card.delta_metric && deltas && card.delta_metric in deltas) {
        var delta = deltas[card.delta_metric];
        var direction = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
        var arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "▬";
        pieces.push(
          el("div", { class: "delta " + direction, text: arrow + " " + delta })
        );
      }
      wrap.appendChild(el("div", { class: "card" }, pieces));
    });
    return wrap;
  }

  function renderD3Graph(section) {
    var wrap = el("div", { class: "viz" });
    var width = 760;
    var height = 460;
    var svg = window.d3
      .select(wrap)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height);

    var nodes = (section.nodes || []).map(function (node) {
      return { id: node.id, label: node.label || node.id, group: node.group };
    });
    var links = (section.links || []).map(function (link) {
      return {
        source: link.source,
        target: link.target,
        value: link.value || 1
      };
    });

    var color = window.d3.scaleOrdinal(window.d3.schemeTableau10);

    var simulation = window.d3
      .forceSimulation(nodes)
      .force(
        "link",
        window.d3
          .forceLink(links)
          .id(function (node) {
            return node.id;
          })
          .distance(section.layout === "dag" ? 90 : 70)
      )
      .force("charge", window.d3.forceManyBody().strength(-220))
      .force("center", window.d3.forceCenter(width / 2, height / 2));

    if (section.layout === "dag") {
      simulation.force(
        "y",
        window.d3.forceY().y(height / 2).strength(0.06)
      );
    }

    var link = svg
      .append("g")
      .selectAll("line")
      .data(links)
      .enter()
      .append("line")
      .attr("class", "link")
      .attr("stroke-width", function (entry) {
        return Math.sqrt(entry.value);
      });

    var node = svg
      .append("g")
      .selectAll("g")
      .data(nodes)
      .enter()
      .append("g")
      .attr("class", "node");

    node
      .append("circle")
      .attr("r", 7)
      .attr("fill", function (entry) {
        return color(entry.group || "default");
      });

    node
      .append("text")
      .attr("x", 10)
      .attr("dy", "0.32em")
      .text(function (entry) {
        return entry.label;
      });

    simulation.on("tick", function () {
      link
        .attr("x1", function (entry) {
          return entry.source.x;
        })
        .attr("y1", function (entry) {
          return entry.source.y;
        })
        .attr("x2", function (entry) {
          return entry.target.x;
        })
        .attr("y2", function (entry) {
          return entry.target.y;
        });
      node.attr("transform", function (entry) {
        return "translate(" + entry.x + "," + entry.y + ")";
      });
    });

    return wrap;
  }

  function renderSankey(section) {
    var wrap = el("div", { class: "viz" });
    var width = 760;
    var height = 460;
    var svg = window.d3
      .select(wrap)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height);

    var indexById = {};
    var nodes = (section.nodes || []).map(function (entry, index) {
      indexById[entry.id] = index;
      return { name: entry.label || entry.id };
    });
    var links = (section.links || []).map(function (entry) {
      return {
        source: indexById[entry.source],
        target: indexById[entry.target],
        value: entry.value || 1
      };
    });

    var sankey = window.d3
      .sankey()
      .nodeWidth(14)
      .nodePadding(12)
      .extent([
        [8, 8],
        [width - 8, height - 8]
      ]);
    var graph = sankey({
      nodes: nodes.map(function (entry) {
        return Object.assign({}, entry);
      }),
      links: links.map(function (entry) {
        return Object.assign({}, entry);
      })
    });

    var color = window.d3.scaleOrdinal(window.d3.schemeTableau10);

    svg
      .append("g")
      .attr("fill", "none")
      .selectAll("path")
      .data(graph.links)
      .enter()
      .append("path")
      .attr("d", window.d3.sankeyLinkHorizontal())
      .attr("stroke", "#5a6473")
      .attr("stroke-opacity", 0.45)
      .attr("stroke-width", function (entry) {
        return Math.max(1, entry.width);
      });

    var nodeGroup = svg
      .append("g")
      .selectAll("g")
      .data(graph.nodes)
      .enter()
      .append("g");

    nodeGroup
      .append("rect")
      .attr("x", function (entry) {
        return entry.x0;
      })
      .attr("y", function (entry) {
        return entry.y0;
      })
      .attr("height", function (entry) {
        return Math.max(1, entry.y1 - entry.y0);
      })
      .attr("width", function (entry) {
        return entry.x1 - entry.x0;
      })
      .attr("fill", function (entry, index) {
        return color(index);
      });

    nodeGroup
      .append("text")
      .attr("x", function (entry) {
        return entry.x0 < width / 2 ? entry.x1 + 6 : entry.x0 - 6;
      })
      .attr("y", function (entry) {
        return (entry.y0 + entry.y1) / 2;
      })
      .attr("dy", "0.32em")
      .attr("text-anchor", function (entry) {
        return entry.x0 < width / 2 ? "start" : "end";
      })
      .attr("fill", "#d6dde6")
      .style("font-size", "11px")
      .text(function (entry) {
        return entry.name;
      });

    return wrap;
  }

  function renderTreemap(section) {
    var wrap = el("div", { class: "viz" });
    var width = 760;
    var height = 460;
    var svg = window.d3
      .select(wrap)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height);

    var root = window.d3
      .hierarchy(section.root)
      .sum(function (entry) {
        return entry.value || 0;
      })
      .sort(function (a, b) {
        return b.value - a.value;
      });

    window.d3.treemap().size([width, height]).padding(2)(root);
    var color = window.d3.scaleOrdinal(window.d3.schemeTableau10);

    var cell = svg
      .selectAll("g")
      .data(root.leaves())
      .enter()
      .append("g")
      .attr("transform", function (entry) {
        return "translate(" + entry.x0 + "," + entry.y0 + ")";
      });

    cell
      .append("rect")
      .attr("width", function (entry) {
        return entry.x1 - entry.x0;
      })
      .attr("height", function (entry) {
        return entry.y1 - entry.y0;
      })
      .attr("fill", function (entry, index) {
        return color(index);
      })
      .attr("opacity", 0.85);

    cell
      .append("text")
      .attr("x", 4)
      .attr("y", 14)
      .attr("fill", "#0f1419")
      .style("font-size", "11px")
      .text(function (entry) {
        return entry.data.name;
      });

    return wrap;
  }

  function renderHeatmap(section) {
    var wrap = el("div", { class: "viz" });
    var xLabels = section.xLabels || [];
    var yLabels = section.yLabels || [];
    var cells = section.cells || [];
    var margin = 110;
    var cellSize = 34;
    var width = margin + xLabels.length * cellSize + 20;
    var height = margin + yLabels.length * cellSize + 20;
    var svg = window.d3
      .select(wrap)
      .append("svg")
      .attr("viewBox", "0 0 " + width + " " + height);

    var values = cells.map(function (cell) {
      return cell.v;
    });
    var minValue = window.d3.min(values);
    var maxValue = window.d3.max(values);
    var interpolator =
      section.colorScale === "diverging"
        ? window.d3.interpolateRdBu
        : window.d3.interpolateBlues;
    var scale =
      section.colorScale === "diverging"
        ? window.d3
            .scaleSequential(function (t) {
              return interpolator(1 - t);
            })
            .domain([
              -Math.max(Math.abs(minValue), Math.abs(maxValue)),
              Math.max(Math.abs(minValue), Math.abs(maxValue))
            ])
        : window.d3.scaleSequential(interpolator).domain([minValue, maxValue]);

    var xIndex = {};
    xLabels.forEach(function (label, index) {
      xIndex[label] = index;
    });
    var yIndex = {};
    yLabels.forEach(function (label, index) {
      yIndex[label] = index;
    });

    cells.forEach(function (cell) {
      var cx = margin + xIndex[cell.x] * cellSize;
      var cy = margin + yIndex[cell.y] * cellSize;
      if (isNaN(cx) || isNaN(cy)) {
        return;
      }
      svg
        .append("rect")
        .attr("x", cx)
        .attr("y", cy)
        .attr("width", cellSize - 2)
        .attr("height", cellSize - 2)
        .attr("fill", scale(cell.v));
      svg
        .append("text")
        .attr("x", cx + cellSize / 2 - 1)
        .attr("y", cy + cellSize / 2)
        .attr("text-anchor", "middle")
        .attr("dy", "0.32em")
        .style("font-size", "10px")
        .attr("fill", "#0f1419")
        .text(cell.v);
    });

    xLabels.forEach(function (label, index) {
      svg
        .append("text")
        .attr("x", margin + index * cellSize + cellSize / 2)
        .attr("y", margin - 8)
        .attr("text-anchor", "middle")
        .style("font-size", "10px")
        .attr("fill", "#8b95a3")
        .text(label);
    });
    yLabels.forEach(function (label, index) {
      svg
        .append("text")
        .attr("x", margin - 8)
        .attr("y", margin + index * cellSize + cellSize / 2)
        .attr("text-anchor", "end")
        .attr("dy", "0.32em")
        .style("font-size", "10px")
        .attr("fill", "#8b95a3")
        .text(label);
    });

    return wrap;
  }

  var mermaidCounter = 0;

  function renderMermaid(section) {
    var wrap = el("div", { class: "viz" });
    mermaidCounter += 1;
    var id = "mermaid-" + mermaidCounter;
    if (window.mermaid) {
      try {
        window.mermaid.mermaidAPI.initialize({ startOnLoad: false, theme: "dark" });
        window.mermaid.mermaidAPI.render(id, section.diagram || "", function (svgCode) {
          wrap.innerHTML = svgCode;
        });
      } catch (error) {
        wrap.appendChild(
          el("div", { class: "placeholder", text: "mermaid render failed: " + error.message })
        );
      }
    } else {
      wrap.appendChild(el("pre", { text: section.diagram || "" }));
    }
    return wrap;
  }

  function renderPlaceholder(section, fragmentId) {
    return el("div", {
      class: "placeholder",
      text:
        "unsupported section type `" +
        section.type +
        "` (fragment `" +
        fragmentId +
        "`)"
    });
  }

  function renderSection(section, fragmentId, deltas) {
    switch (section.type) {
      case "markdown":
        return renderMarkdown(section);
      case "table":
        return renderTable(section);
      case "key-value":
        return renderKeyValue(section);
      case "metric-cards":
        return renderMetricCards(section, deltas);
      case "d3-graph":
        return renderD3Graph(section);
      case "sankey":
        return renderSankey(section);
      case "treemap":
        return renderTreemap(section);
      case "heatmap":
        return renderHeatmap(section);
      case "mermaid":
        return renderMermaid(section);
      default:
        return renderPlaceholder(section, fragmentId);
    }
  }

  function computeDeltas(current, previous) {
    var deltas = {};
    if (!current || !previous) {
      return deltas;
    }
    var currentMetrics = current.metrics || {};
    var previousMetrics = previous.metrics || {};
    Object.keys(currentMetrics).forEach(function (key) {
      if (key in previousMetrics) {
        deltas[key] = currentMetrics[key] - previousMetrics[key];
      }
    });
    return deltas;
  }

  function renderDeltaTable(current, previous) {
    var currentMetrics = current.metrics || {};
    var previousMetrics = previous.metrics || {};
    var shared = Object.keys(currentMetrics).filter(function (key) {
      return key in previousMetrics;
    });
    if (!shared.length) {
      return null;
    }
    var table = el("table", { class: "delta-table" });
    var head = el("tr");
    ["Metric", "Previous", "Current", "Δ", "%"].forEach(function (label) {
      head.appendChild(el("th", { text: label }));
    });
    table.appendChild(el("thead", null, [head]));
    var tbody = el("tbody");
    shared.forEach(function (key) {
      var previousValue = previousMetrics[key];
      var currentValue = currentMetrics[key];
      var delta = currentValue - previousValue;
      var pct =
        previousValue === 0
          ? "—"
          : ((delta / previousValue) * 100).toFixed(1) + "%";
      tbody.appendChild(
        el("tr", null, [
          el("td", { text: key }),
          el("td", { text: String(previousValue) }),
          el("td", { text: String(currentValue) }),
          el("td", { text: (delta > 0 ? "+" : "") + delta }),
          el("td", { text: pct })
        ])
      );
    });
    table.appendChild(tbody);
    return table;
  }

  function renderFragment(target, fragment, deltas) {
    clear(target);
    if (!fragment) {
      target.appendChild(
        el("div", { class: "empty-state", text: "Select a fragment from the navigation." })
      );
      return;
    }
    var header = el("h1", { class: "fragment-title" }, [fragment.title]);
    header.appendChild(el("span", { class: "badge " + fragment.status, text: fragment.status }));
    target.appendChild(header);
    target.appendChild(el("p", { class: "fragment-sub", text: fragment.summary || "" }));

    (fragment.body || []).forEach(function (section) {
      var block = el("div", { class: "section" });
      if (section.title) {
        block.appendChild(el("h3", { text: section.title }));
      }
      block.appendChild(renderSection(section, fragment.id, deltas));
      target.appendChild(block);
    });

    var producer = fragment.producer || {};
    target.appendChild(
      el("p", { class: "fragment-sub" }, [
        "Produced by " +
          (producer.skill || "?") +
          " · " +
          (producer.tool || "?") +
          " " +
          (producer.version || "") +
          " · " +
          (fragment.generated_at || "")
      ])
    );
  }

  function buildNav() {
    var nav = document.getElementById("nav");
    clear(nav);
    var manifest = state.manifest;
    (manifest.categories || []).forEach(function (category) {
      var rollup = { ok: 0, info: 0, warn: 0, error: 0 };
      category.fragments.forEach(function (fragment) {
        if (fragment.status in rollup) {
          rollup[fragment.status] += 1;
        }
      });
      var worst = rollup.error
        ? "error"
        : rollup.warn
        ? "warn"
        : rollup.info
        ? "info"
        : "ok";
      var head = el("div", { class: "category-head" }, [
        category.label,
        el("span", { class: "pill " + worst, text: String(category.fragments.length) })
      ]);
      var group = el("div", { class: "category" }, [head]);
      category.fragments.forEach(function (fragment) {
        var hash = "#" + category.id + "/" + fragment.id;
        var link = el("a", { href: hash, title: fragment.summary || "" }, [
          el("span", { class: "dot " + fragment.status }),
          fragment.title
        ]);
        link.dataset.path = fragment.path;
        link.dataset.category = category.id;
        link.dataset.id = fragment.id;
        group.appendChild(link);
      });
      nav.appendChild(group);
    });
  }

  function buildReleaseHeader() {
    var header = document.getElementById("release-header");
    clear(header);
    var release = state.manifest.release || {};
    var rollup = state.manifest.rollup || {};
    header.appendChild(el("div", null, [release.label || release.id || "Report"]));
    header.appendChild(
      el("div", { class: "release-meta" }, [
        (release.vcs_ref ? release.vcs_ref + " · " : "") +
          (release.git_sha || "no-sha") +
          " · " +
          (release.created_at || "")
      ])
    );
    var pills = el("div", { class: "rollup" });
    ["ok", "info", "warn", "error"].forEach(function (status) {
      pills.appendChild(
        el("span", { class: "pill " + status, text: status + " " + (rollup[status] || 0) })
      );
    });
    header.appendChild(pills);
  }

  function highlightActive() {
    var links = document.querySelectorAll("#nav a");
    Array.prototype.forEach.call(links, function (link) {
      var match =
        link.dataset.category === state.currentCategory &&
        link.dataset.id === state.currentId;
      if (match) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });
  }

  function previousReleasePath() {
    if (!state.releases.length) {
      return null;
    }
    var release = state.releases[state.previousIndex];
    if (!release) {
      return null;
    }
    return (
      "../" +
      release.id +
      "/data/" +
      state.currentCategory +
      "/" +
      state.currentId +
      ".json"
    );
  }

  function renderPreviousPane(currentFragment) {
    var label = document.getElementById("previous-label");
    var body = document.getElementById("pane-previous-body");
    clear(body);
    if (!state.releases.length) {
      label.textContent = "no previous releases";
      return;
    }
    var release = state.releases[state.previousIndex];
    label.textContent = release ? release.label || release.id : "—";

    var path = previousReleasePath();
    if (!path) {
      body.appendChild(el("div", { class: "empty-state", text: "no comparable release" }));
      return;
    }
    getData(path)
      .then(function (fragment) {
        var deltas = computeDeltas(currentFragment, fragment);
        var deltaTable = renderDeltaTable(currentFragment, fragment);
        if (deltaTable) {
          body.appendChild(el("h3", { class: "section", text: "Metric Δ" }));
          body.appendChild(deltaTable);
        }
        renderFragment(body, fragment, computeDeltas(fragment, currentFragment));
      })
      .catch(function () {
        clear(body);
        body.appendChild(
          el("div", {
            class: "placeholder",
            text:
              "fragment `" +
              state.currentId +
              "` not present in " +
              (release ? release.id : "previous release")
          })
        );
      });
  }

  function loadCurrent() {
    var paneCurrent = document.getElementById("pane-current");
    if (!state.currentPath) {
      renderFragment(paneCurrent, null);
      return;
    }
    getData(state.currentPath)
      .then(function (fragment) {
        if (state.splitMode) {
          getData(previousReleasePath() || "")
            .then(function (previous) {
              renderFragment(paneCurrent, fragment, computeDeltas(fragment, previous));
            })
            .catch(function () {
              renderFragment(paneCurrent, fragment, {});
            });
          renderPreviousPane(fragment);
        } else {
          renderFragment(paneCurrent, fragment, {});
        }
      })
      .catch(function (error) {
        clear(paneCurrent);
        paneCurrent.appendChild(
          el("div", { class: "placeholder", text: "failed to load fragment: " + error.message })
        );
      });
  }

  function applyHash() {
    var hash = window.location.hash.replace(/^#/, "");
    var parts = hash.split("/");
    if (parts.length === 2 && parts[0] && parts[1]) {
      state.currentCategory = parts[0];
      state.currentId = parts[1];
      state.currentPath = "data/" + parts[0] + "/" + parts[1] + ".json";
    } else {
      var firstCategory = (state.manifest.categories || [])[0];
      if (firstCategory && firstCategory.fragments.length) {
        var first = firstCategory.fragments[0];
        state.currentCategory = firstCategory.id;
        state.currentId = first.id;
        state.currentPath = first.path;
      }
    }
    highlightActive();
    loadCurrent();
  }

  function setSplitMode(on) {
    state.splitMode = on;
    var toggle = document.getElementById("toggle-split");
    var panePrevious = document.getElementById("pane-previous");
    toggle.setAttribute("aria-pressed", on ? "true" : "false");
    toggle.textContent = on ? "Single view" : "Split view";
    if (on) {
      panePrevious.classList.remove("hidden");
    } else {
      panePrevious.classList.add("hidden");
    }
    loadCurrent();
  }

  function walkPrevious(direction) {
    if (!state.releases.length) {
      return;
    }
    var next = state.previousIndex + direction;
    if (next < 0) {
      next = 0;
    }
    if (next > state.releases.length - 1) {
      next = state.releases.length - 1;
    }
    state.previousIndex = next;
    loadCurrent();
  }

  function loadReleases() {
    var manifestRelease = (state.manifest.release || {}).id;
    return getData("../releases.json")
      .then(function (data) {
        var all = (data && data.releases) || [];
        state.releases = all.filter(function (entry) {
          return entry.id !== manifestRelease;
        });
      })
      .catch(function () {
        state.releases = [];
      });
  }

  function start() {
    getData("data/manifest.json")
      .then(function (manifest) {
        state.manifest = manifest;
        buildReleaseHeader();
        buildNav();
        return loadReleases();
      })
      .then(function () {
        document
          .getElementById("toggle-split")
          .addEventListener("click", function () {
            setSplitMode(!state.splitMode);
          });
        document
          .getElementById("prev-older")
          .addEventListener("click", function () {
            walkPrevious(1);
          });
        document
          .getElementById("prev-newer")
          .addEventListener("click", function () {
            walkPrevious(-1);
          });
        window.addEventListener("keydown", function (event) {
          if (!state.splitMode) {
            return;
          }
          if (event.key === "ArrowLeft") {
            walkPrevious(1);
          } else if (event.key === "ArrowRight") {
            walkPrevious(-1);
          }
        });
        window.addEventListener("hashchange", applyHash);
        applyHash();
      })
      .catch(function (error) {
        document.getElementById("pane-current").appendChild(
          el("div", {
            class: "placeholder",
            text:
              "could not load manifest. If opened via file:// rebuild without --no-embed. (" +
              error.message +
              ")"
          })
        );
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
