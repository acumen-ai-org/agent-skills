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

  var isFileProtocol = window.location.protocol === "file:";

  var fetchCache = {};

  function hasEmbedded(path) {
    return Object.prototype.hasOwnProperty.call(window.__REPORT_DATA__, path);
  }

  function getData(path) {
    if (hasEmbedded(path)) {
      return Promise.resolve(window.__REPORT_DATA__[path]);
    }
    if (isFileProtocol) {
      return Promise.reject(new Error("file:// cannot read " + path));
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

  function embeddedReleases() {
    var doc = window.__REPORT_DATA__["releases.json"];
    if (doc && doc.releases) {
      return doc.releases;
    }
    return [];
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
    previousIndex: 0,
    moduleOptions: ["All"],
    currentModule: "All"
  };

  function moduleColumns(columns) {
    return (columns || []).filter(function (column) {
      return column.type === "module";
    });
  }

  function rowModuleHidden(row, columns) {
    if (state.currentModule === "All") {
      return false;
    }
    return moduleColumns(columns).some(function (column) {
      var value = row[column.key];
      if (value == null || String(value) === "") {
        return false;
      }
      return String(value) !== state.currentModule;
    });
  }

  function sectionModuleHidden(section) {
    if (state.currentModule === "All") {
      return false;
    }
    if (!section || section.module == null || section.module === "") {
      return false;
    }
    return String(section.module) !== state.currentModule;
  }

  function collectModuleValues(fragment, sink) {
    (fragment && fragment.body ? fragment.body : []).forEach(function (section) {
      if (section && section.module != null && section.module !== "") {
        sink[String(section.module)] = true;
      }
      if (section && section.type === "table") {
        var columns = moduleColumns(section.columns);
        if (columns.length) {
          (function walk(rows) {
            (rows || []).forEach(function (row) {
              columns.forEach(function (column) {
                var value = row[column.key];
                if (value != null && String(value) !== "") {
                  sink[String(value)] = true;
                }
              });
              walk(row.children);
            });
          })(section.rows);
        }
      }
    });
  }

  function fragmentPaths() {
    var paths = [];
    (state.manifest.categories || []).forEach(function (category) {
      (category.fragments || []).forEach(function (fragment) {
        if (fragment.path) {
          paths.push(fragment.path);
        }
      });
    });
    return paths;
  }

  function sortModuleOptions(values) {
    var rest = values
      .filter(function (value) {
        return value !== "root";
      })
      .sort(function (a, b) {
        return a.localeCompare(b);
      });
    var ordered = ["All"];
    if (values.indexOf("root") !== -1) {
      ordered.push("root");
    }
    return ordered.concat(rest);
  }

  function renderMarkdown(section) {
    var wrap = el("div", { class: "md-body" });
    var raw = window.marked ? window.marked.parse(section.md || "") : section.md || "";
    wrap.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(raw) : "";
    return wrap;
  }

  function rowMatches(row, columns, filterText) {
    return columns.some(function (column) {
      return String(row[column.key] == null ? "" : row[column.key])
        .toLowerCase()
        .indexOf(filterText) !== -1;
    });
  }

  function subtreeMatches(row, columns, filterText) {
    if (rowMatches(row, columns, filterText)) {
      return true;
    }
    return (row.children || []).some(function (child) {
      return subtreeMatches(child, columns, filterText);
    });
  }

  function sortRows(rows, columns, sortKey, sortDir) {
    if (!sortKey) {
      return rows;
    }
    var sortColumn = columns.filter(function (column) {
      return column.key === sortKey;
    })[0];
    var numeric = sortColumn && sortColumn.type === "number";
    var ordered = rows.slice().sort(function (a, b) {
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
    return ordered.map(function (row) {
      if (!row.children || !row.children.length) {
        return row;
      }
      var copy = {};
      Object.keys(row).forEach(function (key) {
        copy[key] = row[key];
      });
      copy.children = sortRows(row.children, columns, sortKey, sortDir);
      return copy;
    });
  }

  function renderCell(column, value, files) {
    if (column.type === "file" && value != null) {
      var path = String(value);
      var entry = (files || []).filter(function (file) {
        return file.path === path;
      })[0];
      if (entry) {
        var token = el("span", { class: "file-token", text: path });
        token.addEventListener("click", function () {
          openFileModal(entry);
        });
        return el("td", null, [token]);
      }
    }
    return el("td", { text: value == null ? "" : String(value) });
  }

  function renderTable(section) {
    var wrap = el("div");
    var columns = section.columns || [];
    var files = section.files || [];
    var rows = (section.rows || []).slice();
    var sortKey = section.defaultSort ? section.defaultSort.key : null;
    var sortDir = section.defaultSort ? section.defaultSort.dir : "asc";
    var filterText = "";
    var expanded = {};
    var rowSeq = 0;

    function appendRows(tbody, list, depth) {
      list.forEach(function (row) {
        if (rowModuleHidden(row, columns)) {
          return;
        }
        if (filterText && !subtreeMatches(row, columns, filterText)) {
          return;
        }
        if (row.__key == null) {
          rowSeq += 1;
          row.__key = "r" + rowSeq;
        }
        var children = row.children || [];
        var hasChildren = children.length > 0;
        var isOpen = expanded[row.__key] === true;
        var tr = el("tr");
        columns.forEach(function (column, columnIndex) {
          var value = row[column.key];
          var td;
          if (column.type === "file" && value != null && files.length) {
            td = renderCell(column, value, files);
          } else {
            td = el("td", { text: value == null ? "" : String(value) });
          }
          if (columnIndex === 0) {
            td.style.paddingLeft = 10 + depth * 18 + "px";
            if (hasChildren) {
              var toggle = el("span", {
                class: "row-toggle",
                text: isOpen ? "▾" : "▸"
              });
              toggle.addEventListener("click", function () {
                expanded[row.__key] = !isOpen;
                build();
              });
              td.insertBefore(toggle, td.firstChild);
            }
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
        if (hasChildren && (isOpen || filterText)) {
          appendRows(tbody, children, depth + 1);
        }
      });
    }

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

      var ordered = sortRows(rows, columns, sortKey, sortDir);
      var tbody = el("tbody");
      appendRows(tbody, ordered, 0);
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

  function renderD3GraphChord(svg, width, height, nodes, links, color) {
    var indexById = {};
    nodes.forEach(function (node, index) {
      indexById[node.id] = index;
    });
    var size = nodes.length;
    var matrix = nodes.map(function () {
      var row = [];
      for (var i = 0; i < size; i += 1) {
        row.push(0);
      }
      return row;
    });
    links.forEach(function (link) {
      var s = indexById[link.source];
      var t = indexById[link.target];
      if (s == null || t == null) {
        return;
      }
      matrix[s][t] += link.value;
    });

    var outer = Math.min(width, height) / 2 - 70;
    var inner = outer - 12;
    var chords = window.d3
      .chord()
      .padAngle(0.04)
      .sortSubgroups(window.d3.descending)(matrix);
    var arc = window.d3.arc().innerRadius(inner).outerRadius(outer);
    var ribbon = window.d3.ribbon().radius(inner);

    var root = svg
      .append("g")
      .attr("transform", "translate(" + width / 2 + "," + height / 2 + ")");

    var group = root
      .append("g")
      .selectAll("g")
      .data(chords.groups)
      .enter()
      .append("g");

    group
      .append("path")
      .attr("d", arc)
      .attr("fill", function (entry) {
        return color(nodes[entry.index].group || nodes[entry.index].id);
      })
      .attr("stroke", "var(--border)");

    group
      .append("text")
      .each(function (entry) {
        entry.angle = (entry.startAngle + entry.endAngle) / 2;
      })
      .attr("dy", "0.32em")
      .attr("transform", function (entry) {
        return (
          "rotate(" +
          ((entry.angle * 180) / Math.PI - 90) +
          ") translate(" +
          (outer + 8) +
          ")" +
          (entry.angle > Math.PI ? " rotate(180)" : "")
        );
      })
      .attr("text-anchor", function (entry) {
        return entry.angle > Math.PI ? "end" : "start";
      })
      .style("font-size", "11px")
      .attr("fill", "var(--text)")
      .text(function (entry) {
        return nodes[entry.index].label;
      });

    root
      .append("g")
      .attr("fill-opacity", 0.6)
      .selectAll("path")
      .data(chords)
      .enter()
      .append("path")
      .attr("d", ribbon)
      .attr("fill", function (entry) {
        return color(
          nodes[entry.source.index].group || nodes[entry.source.index].id
        );
      })
      .attr("stroke", "var(--border)");
  }

  function renderD3GraphForce(svg, width, height, nodes, links, color, layout) {
    var simulation = window.d3
      .forceSimulation(nodes)
      .force(
        "link",
        window.d3
          .forceLink(links)
          .id(function (node) {
            return node.id;
          })
          .distance(layout === "dag" ? 90 : 70)
      )
      .force("charge", window.d3.forceManyBody().strength(-220))
      .force("center", window.d3.forceCenter(width / 2, height / 2));

    if (layout === "dag") {
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

    if (section.layout === "chord") {
      renderD3GraphChord(svg, width, height, nodes, links, color);
    } else {
      renderD3GraphForce(
        svg,
        width,
        height,
        nodes,
        links,
        color,
        section.layout === "dag" ? "dag" : "force"
      );
    }

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

  function renderImage(section) {
    var wrap = el("div", { class: "viz" });
    var img = el("img", {
      class: "image-body",
      src: section.src || "",
      alt: section.alt || ""
    });
    if (section.title) {
      img.setAttribute("title", section.title);
    }
    wrap.appendChild(img);
    return wrap;
  }

  function openFileModal(entry) {
    var backdrop = document.getElementById("file-modal");
    var title = document.getElementById("file-modal-title");
    var body = document.getElementById("file-modal-body");
    var foot = document.getElementById("file-modal-foot");
    clear(body);
    clear(foot);
    var lang = (entry.lang || "").toLowerCase();
    var label = entry.path + " · " + (entry.lang || "text");
    if (entry.startLine != null) {
      label += " · from line " + entry.startLine;
    }
    title.textContent = label;
    if (lang === "md" || lang === "markdown") {
      var md = el("div", { class: "md-body" });
      var raw = window.marked
        ? window.marked.parse(entry.excerpt || "")
        : entry.excerpt || "";
      md.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(raw) : "";
      body.appendChild(md);
    } else {
      body.appendChild(el("pre", { class: "file-pre", text: entry.excerpt || "" }));
    }
    var served = window.location.protocol !== "file:";
    if (served) {
      var open = el("a", {
        class: "file-open",
        href: entry.path,
        target: "_blank",
        rel: "noopener"
      }, ["Open full file"]);
      foot.appendChild(open);
    } else {
      foot.appendChild(
        el("span", {
          class: "file-open inert",
          title: "Serve the report to open the full file"
        }, ["Open full file (serve the report)"])
      );
    }
    backdrop.classList.remove("hidden");
  }

  function closeFileModal() {
    document.getElementById("file-modal").classList.add("hidden");
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
      case "image":
        return renderImage(section);
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

    function sectionBlock(section) {
      var block = el("div", { class: "section" });
      if (section.title) {
        block.appendChild(el("h3", { text: section.title }));
      }
      block.appendChild(renderSection(section, fragment.id, deltas));
      return block;
    }

    var releaseCol = el("div", { class: "view-col" }, [
      el("div", { class: "view-col-head", text: "This release" })
    ]);
    var deltaCol = el("div", { class: "view-col" }, [
      el("div", { class: "view-col-head", text: "Δ vs previous" })
    ]);
    var releaseCount = 0;
    var deltaCount = 0;
    (fragment.body || []).forEach(function (section) {
      if (sectionModuleHidden(section)) {
        return;
      }
      if (section.view === "delta") {
        deltaCol.appendChild(sectionBlock(section));
        deltaCount += 1;
      } else {
        releaseCol.appendChild(sectionBlock(section));
        releaseCount += 1;
      }
    });
    if (!releaseCount) {
      releaseCol.appendChild(
        el("div", { class: "placeholder", text: "— nothing for this view —" })
      );
    }
    if (!deltaCount) {
      deltaCol.appendChild(
        el("div", { class: "placeholder", text: "— nothing for this view —" })
      );
    }
    target.appendChild(
      el("div", { class: "view-cols" }, [releaseCol, deltaCol])
    );

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

  function orderedCategories() {
    var categories = (state.manifest.categories || []).slice();
    categories.sort(function (a, b) {
      if (a.id === "overview" && b.id !== "overview") {
        return -1;
      }
      if (b.id === "overview" && a.id !== "overview") {
        return 1;
      }
      return String(a.id).localeCompare(String(b.id));
    });
    return categories;
  }

  function overviewLanding() {
    var overview = orderedCategories().filter(function (category) {
      return category.id === "overview";
    })[0];
    if (!overview || !overview.fragments.length) {
      return null;
    }
    var fragments = overview.fragments.slice().sort(function (a, b) {
      return String(a.id).localeCompare(String(b.id));
    });
    return { category: overview.id, fragment: fragments[0] };
  }

  function buildNav() {
    var nav = document.getElementById("nav");
    clear(nav);
    orderedCategories().forEach(function (category) {
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
        var hash = "#" + category.id + "/" + fragment.id + moduleSuffix();
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

  function formatReleaseTitle(release) {
    var date = String(release.created_at || "").slice(0, 10) || "Release";
    var parts = [date];
    if (release.id) {
      parts.push(String(release.id));
    }
    if (release.commit_count != null) {
      parts.push(release.commit_count + " commits");
    }
    return parts.join(" · ");
  }

  function releaseStatusBadge(release) {
    var releases = embeddedReleases();
    if (!releases.length || release.id == null) {
      return null;
    }
    var newest = releases[0];
    if (newest && newest.id === release.id) {
      return el("span", {
        class: "release-badge latest",
        text: "✓ latest"
      });
    }
    return el("span", {
      class: "release-badge superseded",
      text: "⚠ superseded — latest is " + (newest ? newest.id : "?")
    });
  }

  function buildReleaseHeader() {
    var header = document.getElementById("release-header");
    clear(header);
    var release = state.manifest.release || {};
    var rollup = state.manifest.rollup || {};
    var titleRow = el("div", { class: "release-title" }, [
      el("span", { text: formatReleaseTitle(release) })
    ]);
    var badge = releaseStatusBadge(release);
    if (badge) {
      titleRow.appendChild(badge);
    }
    header.appendChild(titleRow);
    var pills = el("div", { class: "rollup" });
    ["ok", "info", "warn", "error"].forEach(function (status) {
      pills.appendChild(
        el("span", { class: "pill " + status, text: status + " " + (rollup[status] || 0) })
      );
    });
    header.appendChild(pills);
  }

  function currentCategoryFragments() {
    var category = orderedCategories().filter(function (entry) {
      return entry.id === state.currentCategory;
    })[0];
    return category ? category.fragments : [];
  }

  function renderCurrent(fragment, deltas) {
    var paneCurrent = document.getElementById("pane-current");
    renderFragment(paneCurrent, fragment, deltas);
    var siblings = currentCategoryFragments();
    if (siblings.length > 1) {
      var menu = el("div", { class: "section-menu" });
      siblings.forEach(function (entry) {
        var tab = el("a", {
          class:
            "section-tab" + (entry.id === state.currentId ? " active" : ""),
          href: "#" + state.currentCategory + "/" + entry.id + moduleSuffix()
        }, [
          el("span", { class: "dot " + entry.status }),
          entry.title
        ]);
        menu.appendChild(tab);
      });
      paneCurrent.insertBefore(menu, paneCurrent.firstChild);
    }
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
    if (isFileProtocol && !hasEmbedded(path)) {
      body.appendChild(
        el("div", {
          class: "placeholder",
          text:
            "Previous-release comparison needs the report served " +
            "(e.g. `python3 -m http.server`) — it can't read sibling " +
            "releases from a file:// page. The current release renders fully."
        })
      );
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
              renderCurrent(fragment, computeDeltas(fragment, previous));
            })
            .catch(function () {
              renderCurrent(fragment, {});
            });
          renderPreviousPane(fragment);
        } else {
          renderCurrent(fragment, {});
        }
      })
      .catch(function (error) {
        clear(paneCurrent);
        paneCurrent.appendChild(
          el("div", { class: "placeholder", text: "failed to load fragment: " + error.message })
        );
      });
  }

  function parseHash() {
    var raw = window.location.hash.replace(/^#/, "");
    var route = raw;
    var module = null;
    var queryAt = raw.indexOf("?");
    if (queryAt !== -1) {
      route = raw.slice(0, queryAt);
      raw
        .slice(queryAt + 1)
        .split("&")
        .forEach(function (pair) {
          var eq = pair.indexOf("=");
          if (eq !== -1 && pair.slice(0, eq) === "module") {
            module = decodeURIComponent(pair.slice(eq + 1));
          }
        });
    }
    return { route: route, module: module };
  }

  function moduleSuffix() {
    if (state.currentModule && state.currentModule !== "All") {
      return "?module=" + encodeURIComponent(state.currentModule);
    }
    return "";
  }

  function routeHash() {
    if (!state.currentCategory || !state.currentId) {
      return "";
    }
    return (
      "#" + state.currentCategory + "/" + state.currentId + moduleSuffix()
    );
  }

  function applyHash() {
    var parsed = parseHash();
    if (parsed.module && state.moduleOptions.indexOf(parsed.module) !== -1) {
      state.currentModule = parsed.module;
    } else {
      state.currentModule = "All";
    }
    var moduleSelect = document.getElementById("module-select");
    if (moduleSelect) {
      moduleSelect.value = state.currentModule;
    }
    var parts = parsed.route.split("/");
    if (parts.length === 2 && parts[0] && parts[1]) {
      state.currentCategory = parts[0];
      state.currentId = parts[1];
      state.currentPath = "data/" + parts[0] + "/" + parts[1] + ".json";
    } else {
      var landing = overviewLanding();
      if (landing) {
        state.currentCategory = landing.category;
        state.currentId = landing.fragment.id;
        state.currentPath = landing.fragment.path;
      } else {
        var firstCategory = orderedCategories()[0];
        if (firstCategory && firstCategory.fragments.length) {
          var first = firstCategory.fragments[0];
          state.currentCategory = firstCategory.id;
          state.currentId = first.id;
          state.currentPath = first.path;
        }
      }
    }
    buildNav();
    highlightActive();
    loadCurrent();
  }

  function setSplitMode(on) {
    state.splitMode = on;
    var toggle = document.getElementById("toggle-split");
    var panePrevious = document.getElementById("pane-previous");
    toggle.setAttribute("aria-pressed", on ? "true" : "false");
    toggle.textContent = on
      ? "Hide previous releases"
      : "Show/hide previous releases";
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

  function buildModuleFilter() {
    var wrap = document.getElementById("module-filter");
    var select = document.getElementById("module-select");
    if (state.moduleOptions.length <= 1) {
      wrap.classList.add("hidden");
      return;
    }
    clear(select);
    state.moduleOptions.forEach(function (value) {
      select.appendChild(el("option", { value: value, text: value }));
    });
    select.value =
      state.moduleOptions.indexOf(state.currentModule) !== -1
        ? state.currentModule
        : "All";
    select.addEventListener("change", function () {
      state.currentModule = select.value;
      var next = routeHash();
      if (next && next !== window.location.hash) {
        window.location.hash = next;
      } else {
        loadCurrent();
      }
    });
    wrap.classList.remove("hidden");
  }

  function computeModuleOptions() {
    var sink = {};
    (state.manifest.modules || []).forEach(function (value) {
      if (value != null && value !== "") {
        sink[String(value)] = true;
      }
    });
    return Promise.all(
      fragmentPaths().map(function (path) {
        return getData(path)
          .then(function (fragment) {
            collectModuleValues(fragment, sink);
          })
          .catch(function () {});
      })
    ).then(function () {
      state.moduleOptions = sortModuleOptions(Object.keys(sink));
    });
  }

  function loadReleases() {
    var manifestRelease = (state.manifest.release || {}).id;
    function adopt(data) {
      var all = (data && data.releases) || [];
      state.releases = all.filter(function (entry) {
        return entry.id !== manifestRelease;
      });
    }
    var embeddedDoc = window.__REPORT_DATA__["releases.json"];
    if (embeddedDoc) {
      adopt(embeddedDoc);
      return Promise.resolve();
    }
    if (isFileProtocol) {
      state.releases = [];
      return Promise.resolve();
    }
    return fetch("../releases.json")
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(adopt)
      .catch(function () {
        state.releases = [];
      });
  }

  function start() {
    getData("data/manifest.json")
      .then(function (manifest) {
        state.manifest = manifest;
        buildReleaseHeader();
        return computeModuleOptions();
      })
      .then(function () {
        buildModuleFilter();
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
        document
          .getElementById("file-modal-close")
          .addEventListener("click", closeFileModal);
        document
          .getElementById("file-modal")
          .addEventListener("click", function (event) {
            if (event.target.id === "file-modal") {
              closeFileModal();
            }
          });
        window.addEventListener("keydown", function (event) {
          if (event.key === "Escape") {
            closeFileModal();
          }
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
