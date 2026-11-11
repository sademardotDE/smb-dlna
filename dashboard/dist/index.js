// smb-dlna Dashboard-Tab: Samba (smb/nmb) und MiniDLNA — Status, Start/Stopp, Autostart.
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

  var Card = components.Card || function (p) { return h("div", p); };
  var CardHeader = components.CardHeader || function (p) { return h("div", p); };
  var CardTitle = components.CardTitle || function (p) { return h("h3", p); };
  var CardContent = components.CardContent || function (p) { return h("div", p); };
  var Badge = components.Badge || function (p) { return h("span", p); };
  var Button = components.Button || function (p) { return h("button", p); };

  var API_BASE = "/api/plugins/smb-dlna";
  var LABELS = { smb: "Samba (smb + nmb)", dlna: "MiniDLNA" };

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

    if (error && !data) return h(Card, null, h(CardContent, null, h("p", null, "Fehler: " + error)));
    if (!data) return h("div", null, "Lade Dienste …");

    var services = data.services || {};
    return h(Card, null,
      h(CardHeader, null, h(CardTitle, null, "Samba & MiniDLNA")),
      h(CardContent, null,
        Object.keys(services).map(function (name) {
          var svc = services[name] || {};
          var units = svc.units || {};
          var active = !!svc.active;
          var enabled = !!svc.enabled;
          return h("div", {
            key: name,
            style: {
              border: "1px solid var(--ui-stroke-secondary, rgba(128,128,128,.25))",
              borderRadius: "8px",
              padding: "12px",
              marginBottom: "10px"
            }
          },
            h("div", { style: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" } },
              h("strong", null, LABELS[name] || name),
              h(Badge, null, active ? "läuft" : "gestoppt"),
              h(Badge, null, enabled ? "Autostart an" : "Autostart aus")
            ),
            h("div", { style: { fontSize: "12px", color: "var(--ui-text-secondary, #888)", marginTop: "4px" } },
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
        }),
        error ? h("p", { style: { color: "var(--ui-danger, #d33)" } }, "Fehler: " + error) : null
      )
    );
  }

  window.__HERMES_PLUGINS__.register("smb-dlna", Page);
})();
