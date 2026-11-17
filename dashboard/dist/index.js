// smb-dlna Dashboard-Tab: Samba (smb/nmb), MiniDLNA — Status, Start/Stopp,
// Autostart — plus Medienordner (media_dir) mit Ordner-Explorer und Vorschau.
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;

  var React = SDK.React;
  var h = React.createElement;
  var hooks = SDK.hooks || {};
  var components = SDK.components || {};
  var useState = hooks.useState || React.useState;
  var useEffect = hooks.useEffect || React.useEffect;
  var useMemo = hooks.useMemo || React.useMemo;
  var useRef = hooks.useRef || React.useRef;

  var Card = components.Card || function (p) { return h("div", p); };
  var CardHeader = components.CardHeader || function (p) { return h("div", p); };
  var CardTitle = components.CardTitle || function (p) { return h("h3", p); };
  var CardContent = components.CardContent || function (p) { return h("div", p); };
  var Badge = components.Badge || function (p) { return h("span", p); };
  var Button = components.Button || function (p) { return h("button", p); };
  var Input = components.Input || function (p) { return h("input", p); };
  var Label = components.Label || function (p) { return h("label", p); };
  var Select = components.Select;
  var SelectOption = components.SelectOption;
  var Checkbox = components.Checkbox;
  var Separator = components.Separator;
  var Dialog = components.Dialog;
  var DialogContent = components.DialogContent;
  var DialogHeader = components.DialogHeader;
  var DialogTitle = components.DialogTitle;
  var DialogDescription = components.DialogDescription;
  var DialogFooter = components.DialogFooter;
  var DialogClose = components.DialogClose;

  var API_BASE = "/api/plugins/smb-dlna";
  var LABELS = { smb: "Samba (smb + nmb)", dlna: "MiniDLNA" };
  var TYPE_LABELS = { A: "Audio", V: "Video", P: "Bilder" };
  var TYPE_ORDER = ["V", "A", "P"];
  var MOUNTS = ["/home", "/media", "/mnt", "/srv", "/run/media", "/data"];

  var mono = { fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" };
  var muted = { fontSize: "12px", color: "var(--ui-text-secondary, #888)" };
  var rowBox = {
    border: "1px solid var(--ui-stroke-secondary, rgba(128,128,128,.25))",
    borderRadius: "8px",
    padding: "12px",
    marginBottom: "10px"
  };

  // ------------------------------------------------------------------ Hilfen
  function api(path, options) {
    return SDK.fetchJSON(API_BASE + path, options);
  }
  function apiJSON(method, path, body) {
    return api(path, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  }
  function errText(err) {
    return err && err.message ? err.message : String(err);
  }
  function sameEntries(a, b) {
    return JSON.stringify(a || []) === JSON.stringify(b || []);
  }
  function countText(counts) {
    if (!counts) return "";
    var text = counts.video + " Videos · " + counts.audio + " Audio · " +
      counts.image + " Bilder";
    return text;
  }
  function parentOf(path) {
    if (!path || path === "/") return null;
    var cut = path.replace(/\/+$/, "").split("/");
    cut.pop();
    return cut.join("/") || "/";
  }

  // --------------------------------------------------------------- Ordnerwahl
  function FolderExplorer(props) {
    var open = props.open;
    var startPath = props.startPath || "/";
    var state = useState(null);
    var view = state[0], setView = state[1];
    var errState = useState(null);
    var error = errState[0], setError = errState[1];
    var hiddenState = useState(false);
    var hidden = hiddenState[0], setHidden = hiddenState[1];
    var loadRef = useRef(0);

    useEffect(function () {
      if (!open) return;
      setView(null);
      setError(null);
      setHidden(false);
      loadRef.current = 0;
      load(startPath);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, startPath]);

    function load(path, note) {
      if (!path) return;
      var id = ++loadRef.current;
      api("/browse?path=" + encodeURIComponent(path) + "&show_hidden=" + (hidden ? "true" : "false"))
        .then(function (r) {
          if (loadRef.current !== id) return;
          setView(r);
          setError(note || null);
        })
        .catch(function (err) {
          if (loadRef.current !== id) return;
          // Verzeichnis nicht erreichbar → auf den übergeordneten Pfad wechseln
          var parent = parentOf(path);
          if (parent && parent !== path) {
            load(parent, "„" + path + "“ ist nicht erreichbar – gewechselt zu „" + parent + "“.");
            return;
          }
          setError(errText(err));
        });
    }

    function toggleHidden() {
      var next = !hidden;
      setHidden(next);
      var path = (view && view.path) || startPath;
      var id = ++loadRef.current;
      api("/browse?path=" + encodeURIComponent(path) + "&show_hidden=" + (next ? "true" : "false"))
        .then(function (r) {
          if (loadRef.current !== id) return;
          setView(r);
          setError(null);
        })
        .catch(function (err) {
          if (loadRef.current !== id) return;
          setError(errText(err));
        });
    }

    var current = (view && view.path) || startPath;

    var body;
    if (error && !view) {
      body = h("p", { style: { color: "var(--ui-danger, #d33)" } }, "Fehler: " + error);
    } else if (!view) {
      body = h("p", { style: muted }, "Lade Verzeichnisse …");
    } else if (!view.entries || !view.entries.length) {
      body = h("p", { style: muted },
        "Keine Unterverzeichnisse – dieses Verzeichnis kann gewählt werden.");
    } else {
      body = h("div", {
        style: {
          maxHeight: "46vh",
          overflowY: "auto",
          border: "1px solid var(--ui-stroke-secondary, rgba(128,128,128,.2))",
          borderRadius: "6px"
        }
      }, view.entries.map(function (entry) {
        return h("button", {
          key: entry.path,
          type: "button",
          onClick: function () { load(entry.path); },
          style: {
            display: "flex",
            alignItems: "center",
            gap: "8px",
            width: "100%",
            padding: "7px 10px",
            background: "transparent",
            border: "0",
            borderBottom: "1px solid var(--ui-stroke-secondary, rgba(128,128,128,.12))",
            color: "var(--ui-text-primary, inherit)",
            textAlign: "left",
            cursor: "pointer",
            fontSize: "13px"
          }
        },
          h("span", { style: { opacity: 0.6 } }, "▸"),
          h("span", { style: mono }, entry.name)
        );
      }));
    }

    var controls = h("div", {
      style: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }
    },
      h(Button, {
        size: "sm",
        ghost: true,
        disabled: !view || !view.parent,
        onClick: function () { if (view && view.parent) load(view.parent); }
      }, "Nach oben"),
      h("div", { style: { display: "flex", gap: "6px", alignItems: "center" } },
        Checkbox
          ? h(Checkbox, {
              checked: hidden,
              onCheckedChange: function () { toggleHidden(); },
              id: "smb-dlna-hidden"
            })
          : null,
        h(Label, {
          htmlFor: "smb-dlna-hidden",
          style: { fontSize: "12px", cursor: "pointer", userSelect: "none" }
        }, "Versteckte zeigen")
      ),
      MOUNTS.map(function (mount) {
        return h(Button, {
          key: mount,
          size: "sm",
          ghost: true,
          onClick: function () { load(mount); }
        }, mount);
      })
    );

    var chooser = Dialog
      ? h(Dialog, { open: open, onOpenChange: props.onClose },
          h(DialogContent, { className: "max-w-2xl" },
            h(DialogHeader, null,
              h(DialogTitle, null, "Ordner auswählen"),
              h(DialogDescription, null, "Navigiere zum Ordner, der die Medien-Dateien enthält.")
            ),
            h("div", {
              style: {
                display: "flex",
                gap: "8px",
                alignItems: "center",
                marginBottom: "8px",
                flexWrap: "wrap"
              }
            },
              h("span", { style: Object.assign({ fontWeight: 600 }, mono) }, current),
              view && view.truncated
                ? h(Badge, null, "gekürzt auf " + (view.entries || []).length)
                : null
            ),
            controls,
            h("div", { style: { marginTop: "8px" } }, body),
            error ? h("p", { style: { color: "var(--ui-danger, #d33)", fontSize: "12px" } },
              "Hinweis: " + error) : null,
            h(DialogFooter, { style: { marginTop: "12px", justifyContent: "space-between" } },
              h("span", { style: mono }, current),
              h("div", { style: { display: "flex", gap: "8px" } },
                h(DialogClose, { asChild: true },
                  h(Button, { ghost: true }, "Abbrechen")),
                h(Button, {
                  onClick: function () { props.onPick(current); }
                }, "Diesen Ordner wählen")
              )
            )
          )
        )
      : null;

    // Fallback ohne SDK-Dialog: einfaches Overlay
    if (!Dialog) {
      if (!open) return null;
      chooser = h("div", {
        style: {
          position: "fixed", inset: 0, zIndex: 1000,
          background: "rgba(0,0,0,.55)",
          display: "flex", alignItems: "center", justifyContent: "center"
        },
        onClick: props.onClose
      },
        h("div", {
          style: {
            background: "var(--ui-background, #1b1b1b)", borderRadius: "10px",
            padding: "16px", width: "min(680px, 92vw)", maxHeight: "84vh",
            overflow: "auto"
          },
          onClick: function (e) { e.stopPropagation(); }
        },
          h("h3", { style: { marginTop: 0 } }, "Ordner auswählen"),
          h("div", { style: { fontWeight: 600, marginBottom: "8px" } }, current),
          controls,
          h("div", { style: { marginTop: "8px" } }, body),
          h("div", {
            style: { display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: "12px" }
          },
            h(Button, { ghost: true, onClick: props.onClose }, "Abbrechen"),
            h(Button, { onClick: function () { props.onPick(current); } }, "Diesen Ordner wählen")
          )
        )
      );
    }
    return chooser;
  }

  // ------------------------------------------------------------ Medienordner
  function MediaCard() {
    var state = useState(null);
    var data = state[0], setData = state[1];
    var errState = useState(null);
    var error = errState[0], setError = errState[1];
    var editState = useState([]);
    var edits = editState[0], setEdits = editState[1];
    var savedState = useState([]);
    var saved = savedState[0], setSaved = savedState[1];
    var restartState = useState(false);
    var restart = restartState[0], setRestart = restartState[1];
    var busyState = useState("");
    var busy = busyState[0], setBusy = busyState[1];
    var explorerState = useState(null);
    var explorer = explorerState[0], setExplorer = explorerState[1];
    var infoState = useState("");
    var info = infoState[0], setInfo = infoState[1];

    function load() {
      api("/media-config")
        .then(function (r) {
          var entries = (r.entries || []).map(function (e) {
            return { type: e.type || "V", path: e.path };
          });
          setData(r);
          setEdits(entries);
          setSaved(entries);
          setError(null);
        })
        .catch(function (err) { setError(errText(err)); });
    }

    useEffect(function () {
      load();
    }, []);

    var dirty = !sameEntries(edits, saved);

    function update(index, patch) {
      setEdits(function (prev) {
        var next = prev.slice();
        next[index] = Object.assign({}, next[index], patch);
        return next;
      });
      setInfo("");
    }

    function remove(index) {
      setEdits(function (prev) { return prev.filter(function (_, i) { return i !== index; }); });
      setInfo("");
    }

    function add() {
      // Eintrag entsteht erst, wenn ein Ordner gewählt wurde
      setExplorer({ index: -1, startPath: "/home" });
      setInfo("");
    }

    function pick(path) {
      if (!explorer) return;
      var index = explorer.index;
      setExplorer(null);
      if (index === -1) {
        // „Ordner hinzufügen“ → Eintrag erst mit gesetztem Pfad anlegen
        setEdits(function (prev) {
          return prev.concat([{ type: "V", path: path }]);
        });
        setInfo("");
        return;
      }
      if (index >= 0 && index < edits.length) {
        update(index, { path: path });
      }
    }

    function save() {
      var missing = edits.filter(function (e) { return !e.path; });
      if (missing.length) {
        setError("Bitte für jeden Eintrag einen Ordner auswählen.");
        return;
      }
      setBusy("save");
      setError(null);
      setInfo("");
      apiJSON("POST", "/media-config", { entries: edits, restart: restart })
        .then(function (r) {
          setInfo(r.written + " Eintrag(e) gespeichert" +
            (r.backup ? " · Sicherung: " + r.backup : "") +
            (r.restart
              ? (r.restart.ok ? " · MiniDLNA neu gestartet" : " · Start fehlgeschlagen: " + r.restart.error)
              : ""));
          load();
        })
        .catch(function (err) { setError(errText(err)); })
        .then(function () { setBusy(""); });
    }

    var previewByPath = {};
    ((data && data.preview) || []).forEach(function (item) {
      previewByPath[item.path] = item;
    });

    function previewLine(path) {
      if (!path) return "Ordner nicht gewählt";
      var item = previewByPath[path];
      if (!item) return "";
      if (item.error) return "nicht lesbar: " + item.error;
      return countText(item.counts) + (item.complete === false ? " · gekürzt gezählt" : "");
    }

    var explorerNode = explorer
      ? h(FolderExplorer, {
          open: true,
          startPath: explorer.startPath,
          onClose: function () { setExplorer(null); },
          onPick: pick
        })
      : null;

    return h(Card, null,
      h(CardHeader, { style: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px", flexWrap: "wrap" } },
        h(CardTitle, null, "Medienordner"),
        h("span", { style: muted }, data && data.conf ? data.conf : "")
      ),
      h(CardContent, null,
        !data && !error ? h("p", { style: muted }, "Lade Konfiguration …") : null,

        data && data.exists === false
          ? h("p", { style: muted }, "Hinweis: " + (data.note || "Konfigurationsdatei fehlt."))
          : null,

        edits.length
          ? edits.map(function (entry, index) {
              return h("div", {
                key: index,
                style: Object.assign({}, rowBox, { marginBottom: "8px" })
              },
                h("div", {
                  style: {
                    display: "flex",
                    gap: "8px",
                    alignItems: "center",
                    flexWrap: "wrap"
                  }
                },
                  Select && SelectOption
                    ? h(Select, {
                        value: entry.type || "V",
                        onValueChange: function (value) { update(index, { type: value }); },
                        style: { width: "130px" }
                      }, TYPE_ORDER.map(function (t) {
                        return h(SelectOption, { key: t, value: t },
                          t + " · " + TYPE_LABELS[t]);
                      }))
                    : h("span", { style: { fontWeight: 700 } }, entry.type || "V"),
                  h("span", {
                    style: Object.assign({ flex: "1 1 220px" }, mono,
                      entry.path ? null : { color: "var(--ui-danger, #d33)" })
                  }, entry.path || "Ordner wählen …"),
                  h(Button, {
                    size: "sm",
                    ghost: true,
                    onClick: function () {
                      setExplorer({
                        index: index,
                        startPath: entry.path || "/home"
                      });
                    }
                  }, entry.path ? "Ändern" : "Auswählen"),
                  h(Button, {
                    size: "sm",
                    ghost: true,
                    destructive: true,
                    onClick: function () { remove(index); }
                  }, "Entfernen")
                ),
                h("div", { style: Object.assign({ marginTop: "4px" }, muted) },
                  previewLine(entry.path))
              );
            })
          : h("p", { style: muted },
              "Noch keine Medienordner hinterlegt – MiniDLNA indexiert derzeit keinen Ordner."),

        h("div", { style: { display: "flex", gap: "8px", marginTop: "4px", flexWrap: "wrap" } },
          h(Button, { size: "sm", onClick: add }, "Ordner hinzufügen"),
          MOUNTS.slice(0, 3).map(function (mount) {
            return h(Button, {
              key: mount,
              size: "sm",
              ghost: true,
              onClick: function () {
                setEdits(function (prev) {
                  return prev.concat([{ type: "V", path: mount }]);
                });
              }
            }, "+ " + mount);
          })
        ),

        h(Separator || "hr", { style: { margin: "12px 0" } }),

        h("div", {
          style: { display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }
        },
          Checkbox && Label
            ? h("div", { style: { display: "flex", gap: "6px", alignItems: "center" } },
                h(Checkbox, {
                  checked: restart,
                  onCheckedChange: function (checked) { setRestart(checked === true); },
                  id: "smb-dlna-restart"
                }),
                h(Label, {
                  htmlFor: "smb-dlna-restart",
                  style: { fontSize: "12px", cursor: "pointer", userSelect: "none" }
                }, "MiniDLNA nach dem Speichern neu starten")
              )
            : null,
          h("span", { style: { flex: "1 1 auto" } }),
          dirty ? h(Badge, null, "ungespeichert") : h("span", { style: muted }, "alles gespeichert"),
          h(Button, {
            disabled: !dirty || !!busy,
            onClick: save
          }, busy === "save" ? "Speichert …" : "Speichern")
        ),

        info ? h("p", { style: Object.assign({ marginTop: "8px" }, muted) }, info) : null,
        error ? h("p", { style: { color: "var(--ui-danger, #d33)", fontSize: "12px", marginTop: "8px" } },
          "Fehler: " + error) : null
      ),
      explorerNode
    );
  }

  // ------------------------------------------------------------------ Seiten
  function Page() {
    var state = useState(null);
    var data = state[0], setData = state[1];
    var errState = useState(null);
    var error = errState[0], setError = errState[1];
    var busyState = useState({});
    var busy = busyState[0], setBusy = busyState[1];

    function load() {
      api("/services")
        .then(function (r) { setData(r); setError(null); })
        .catch(function (err) { setError(errText(err)); });
    }

    useEffect(function () {
      load();
      var timer = setInterval(load, 10000);
      return function () { clearInterval(timer); };
    }, []);

    function act(service, action) {
      setBusy(function (prev) { var n = Object.assign({}, prev); n[service + action] = true; return n; });
      setError(null);
      apiJSON("POST", "/services/" + service + "/" + action, {})
        .then(function () { load(); })
        .catch(function (err) { setError(errText(err)); })
        .then(function () {
          setBusy(function (prev) { var n = Object.assign({}, prev); delete n[service + action]; return n; });
        });
    }

    var servicesCard = h(Card, null,
      h(CardHeader, null, h(CardTitle, null, "Samba & MiniDLNA")),
      h(CardContent, null,
        !data && !error ? h("div", null, "Lade Dienste …") : null,
        error && !data ? h("p", null, "Fehler: " + error) : null,
        data
          ? Object.keys(data.services || {}).map(function (name) {
              var svc = data.services[name] || {};
              var units = svc.units || {};
              var active = !!svc.active;
              var enabled = !!svc.enabled;
              return h("div", { key: name, style: rowBox },
                h("div", { style: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" } },
                  h("strong", null, LABELS[name] || name),
                  h(Badge, null, active ? "läuft" : "gestoppt"),
                  h(Badge, null, enabled ? "Autostart an" : "Autostart aus")
                ),
                h("div", { style: muted },
                  Object.keys(units).map(function (unit) {
                    var info = units[unit] || {};
                    return unit + ": " + (info.active ? "aktiv" : "inaktiv");
                  }).join(" · ")
                ),
                h("div", { style: { marginTop: "8px", display: "flex", gap: "8px", flexWrap: "wrap" } },
                  h(Button, {
                    onClick: function () { act(name, active ? "stop" : "start"); },
                    disabled: busy[name + "start"] || busy[name + "stop"]
                  }, active ? "Stoppen" : "Starten"),
                  h(Button, {
                    onClick: function () { act(name, enabled ? "disable" : "enable"); },
                    disabled: busy[name + "enable"] || busy[name + "disable"]
                  }, enabled ? "Autostart aus" : "Autostart an")
                )
              );
            })
          : null,
        error && data ? h("p", { style: { color: "var(--ui-danger, #d33)" } }, "Fehler: " + error) : null
      )
    );

    return h("div", { style: { padding: "16px", maxWidth: "860px" } },
      servicesCard,
      h(MediaCard, null)
    );
  }

  window.__HERMES_PLUGINS__.register("smb-dlna", Page);
})();
