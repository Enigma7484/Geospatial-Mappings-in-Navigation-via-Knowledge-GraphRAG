import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const artifactPath = require.resolve("@oai/artifact-tool");
const {
  Presentation,
  PresentationFile,
  row,
  column,
  grid,
  layers,
  panel,
  text,
  image,
  shape,
  chart,
  rule,
  fill,
  hug,
  fixed,
  wrap,
  grow,
  fr,
  auto,
} = await import(pathToFileURL(artifactPath).href);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workspace = path.resolve(__dirname, "..");
const outputDir = path.join(workspace, "output");
const scratchDir = path.join(workspace, "scratch_v2");
const previewDir = path.join(scratchDir, "previews");
const assetDir = path.join(__dirname, "assets");

fs.mkdirSync(outputDir, { recursive: true });
fs.mkdirSync(previewDir, { recursive: true });

const routeFieldDataUrl = `data:image/png;base64,${fs.readFileSync(path.join(assetDir, "route_trace_field.png")).toString("base64")}`;

const W = 1920;
const H = 1080;
const C = {
  night: "#07110E",
  night2: "#0B1713",
  ink: "#10231F",
  paper: "#F5F7F2",
  mist: "#CFE3D8",
  muted: "#87A79A",
  faint: "#27423A",
  green: "#48D597",
  green2: "#0EA67A",
  amber: "#F5B84C",
  coral: "#FF7660",
  blue: "#7EA6FF",
  white: "#FFFFFF",
};

const font = "Aptos";
const mono = "Cascadia Mono";

const p = Presentation.create({ slideSize: { width: W, height: H } });

function slide(bg = C.night) {
  const s = p.slides.add();
  s.compose(layers({ width: fill, height: fill }, [shape({ width: fill, height: fill, fill: bg })]), {
    frame: { left: 0, top: 0, width: W, height: H },
    baseUnit: 8,
  });
  return s;
}

function eyebrow(value, color = C.green) {
  return text(value.toUpperCase(), {
    width: wrap(760),
    height: hug,
    style: { fontFace: font, fontSize: 15, bold: true, color },
  });
}

function bigTitle(value, color = C.white, size = 62, width = 1200) {
  return text(value, {
    name: "slide-title",
    width: wrap(width),
    height: hug,
    style: { fontFace: font, fontSize: size, bold: true, color },
  });
}

function body(value, color = C.mist, size = 25, width = 1050) {
  return text(value, {
    width: wrap(width),
    height: hug,
    style: { fontFace: font, fontSize: size, color },
  });
}

function metric(value, label, color = C.green, size = 64) {
  return column({ width: fill, height: hug, gap: 6 }, [
    text(value, {
      width: fill,
      height: hug,
      style: { fontFace: font, fontSize: size, bold: true, color },
    }),
    text(label, {
      width: fill,
      height: hug,
      style: { fontFace: font, fontSize: 17, color: C.muted },
    }),
  ]);
}

function band(label, value, color = C.green) {
  return row({ width: fill, height: hug, gap: 18 }, [
    shape({ width: fixed(8), height: fixed(72), fill: color }),
    column({ width: fill, height: hug, gap: 5 }, [
      eyebrow(label, color),
      text(value, {
        width: fill,
        height: hug,
        style: { fontFace: font, fontSize: 25, bold: true, color: C.white },
      }),
    ]),
  ]);
}

function lightBand(label, value, color = C.green2) {
  return row({ width: fill, height: hug, gap: 18 }, [
    shape({ width: fixed(8), height: fixed(72), fill: color }),
    column({ width: fill, height: hug, gap: 5 }, [
      eyebrow(label, color),
      text(value, {
        width: fill,
        height: hug,
        style: { fontFace: font, fontSize: 25, bold: true, color: C.ink },
      }),
    ]),
  ]);
}

function footer(value, color = C.muted) {
  return text(value, {
    name: "footer",
    width: fill,
    height: hug,
    style: { fontFace: font, fontSize: 13, color },
  });
}

function stageTitle(kicker, title, subtitle = "") {
  return column({ width: fill, height: hug, gap: 18 }, [
    eyebrow(kicker),
    bigTitle(title, C.white, 58, 1250),
    subtitle ? body(subtitle, C.mist, 23, 1120) : shape({ width: fixed(1), height: fixed(1) }),
    rule({ width: fixed(172), stroke: C.green, weight: 5 }),
  ]);
}

// 1. Cover
{
  const s = slide(C.night);
  s.compose(
    layers({ width: fill, height: fill }, [
      image({ dataUrl: routeFieldDataUrl, contentType: "image/png", width: fill, height: fill, fit: "cover", alt: "OSM route field" }),
      shape({ width: fill, height: fill, fill: "#07110EDD" }),
      grid(
        { width: fill, height: fill, columns: [fr(1.05), fr(0.95)], rows: [fr(1), auto], padding: { x: 92, y: 72 }, columnGap: 36 },
        [
          column({ width: fill, height: fill, gap: 22 }, [
            eyebrow("Aker AI Platform Engineering"),
            text("RouteGraph", {
              width: fill,
              height: hug,
              style: { fontFace: font, fontSize: 108, bold: true, color: C.white },
            }),
            text("RAG", {
              width: fill,
              height: hug,
              style: { fontFace: font, fontSize: 108, bold: true, color: C.green },
            }),
            body("A product pitch for preference-aware route ranking from noisy geospatial signals.", C.mist, 30, 760),
          ]),
          column({ width: fill, height: fill, gap: 26, justify: "end" }, [
            band("system shape", "FastAPI service, OSMnx graph pipeline, dynamic profiles, SBERT ranking", C.green),
            band("interview angle", "End-to-end AI system design with real caveats, not demo theater", C.amber),
          ]),
          footer("Built from the current repository artifacts and Aker AI Platform public role context.", "#8FAEA0"),
        ],
      ),
    ]),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 2. Product thesis
{
  const s = slide(C.paper);
  s.compose(
    grid(
      { width: fill, height: fill, columns: [fr(1.05), fr(0.95)], rows: [fr(1), auto], padding: { x: 92, y: 74 }, columnGap: 64 },
      [
        column({ width: fill, height: fill, gap: 22 }, [
          eyebrow("product thesis", C.green2),
          bigTitle("A route is an operational decision, not a polyline.", C.ink, 66, 820),
          body("The product turns messy movement traces and OSM context into ranked, explainable choices: the same platform pattern Aker needs for investment, operations, resident experience, and internal knowledge tools.", "#526D64", 28, 760),
        ]),
        column({ width: fill, height: fill, gap: 34, justify: "center" }, [
          metric("messy data", "public OSM traces, temporal context, incomplete labels", C.coral, 52),
          rule({ width: fill, stroke: "#D6E2DC", weight: 2 }),
          metric("structured memory", "features, profile weights, route summaries", C.green2, 52),
          rule({ width: fill, stroke: "#D6E2DC", weight: 2 }),
          metric("ranked action", "candidate routes with scores and diagnostics", C.amber, 52),
        ]),
        footer("Aker fit: internal AI platform work is about turning operational data into decisions with provenance."),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 3. Live product moment
{
  const s = slide(C.night2);
  s.compose(
    grid(
      { width: fill, height: fill, columns: [fr(0.88), fr(1.12)], rows: [auto, fr(1), auto], padding: { x: 86, y: 66 }, columnGap: 58, rowGap: 40 },
      [
        stageTitle("product surface", "Ask like a human. Rank like a system.", "The backend combines natural-language preference, temporal context, user history, and candidate route features."),
        shape({ width: fixed(1), height: fixed(1) }),
        column({ width: fill, height: fill, gap: 30 }, [
          text("Prefer quieter walking routes near parks and away from major roads.", {
            width: wrap(720),
            height: hug,
            style: { fontFace: font, fontSize: 42, bold: true, color: C.white },
          }),
          row({ width: fill, height: hug, gap: 34 }, [
            metric("prompt", "semantic route-summary match", C.blue, 38),
            metric("profile", "dynamic feature weights", C.green, 38),
          ]),
          row({ width: fill, height: hug, gap: 34 }, [
            metric("hybrid", "0.75 profile + 0.25 SBERT", C.amber, 38),
            metric("explain", "features, scores, coordinates", C.coral, 38),
          ]),
        ]),
        column({ width: fill, height: fill, gap: 22 }, [
          band("input", "origin, destination, preference, timestamp, user_id", C.blue),
          band("candidate generation", "k diverse walking routes under length, scenic, safe, and simple costs", C.green),
          band("ranking", "same candidate pool scored by random, shortest, profile, prompt/SBERT, hybrid", C.amber),
          band("response", "ranked route list with component scores, features, summary, profile explanation", C.coral),
        ]),
        footer("Current backend endpoint: /rank-routes."),
        shape({ width: fixed(1), height: fixed(1) }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 4. Visual evidence
{
  const s = slide(C.night);
  s.compose(
    layers({ width: fill, height: fill }, [
      image({ dataUrl: routeFieldDataUrl, contentType: "image/png", width: fill, height: fill, fit: "cover", alt: "Route trace field" }),
      shape({ width: fill, height: fill, fill: "#07110EB6" }),
      grid(
        { width: fill, height: fill, columns: [fr(0.75), fr(1.25)], rows: [fr(1), auto], padding: { x: 86, y: 68 }, columnGap: 56 },
        [
          column({ width: fill, height: fill, gap: 24 }, [
            eyebrow("data reality"),
            bigTitle("The model only earns trust if the reconstruction does.", C.white, 58, 690),
            body("This route field is generated from actual pseudo-history records in the repo: raw public GPS samples reconstructed onto OSM walking geometry.", C.mist, 25, 650),
          ]),
          shape({ width: fill, height: fill }),
          footer("Use the precise wording: OSM-derived historical movement signals, not clean per-user histories.", "#9AB9AC"),
        ],
      ),
    ]),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 5. Architecture
{
  const s = slide(C.paper);
  s.compose(
    grid(
      { width: fill, height: fill, columns: [fr(1)], rows: [auto, fr(1), auto], padding: { x: 82, y: 62 }, rowGap: 40 },
      [
        column({ width: fill, height: hug, gap: 14 }, [
          eyebrow("system map", C.green2),
          bigTitle("One route representation flows through the whole system.", C.ink, 56, 1320),
          body("That is the important design choice: the model-facing text and the numerical scorer are derived from the same OSM feature object.", "#526D64", 23, 1240),
        ]),
        grid(
          { width: fill, height: fill, columns: [fr(1), fr(1), fr(1), fr(1)], rows: [fr(1), fr(1)], columnGap: 28, rowGap: 26 },
          [
            lightBand("01 probe", "OSM public GPS trackpoints", C.blue),
            lightBand("02 segment", "time gaps, jumps, useful movement filters", C.green2),
            lightBand("03 match", "nearest nodes plus shortest-path stitching", C.amber),
            lightBand("04 extract", "road mix, parks, turns, lighting, crossings", C.coral),
            lightBand("05 profile", "contextual weights from prior signals", C.blue),
            lightBand("06 generate", "diverse OSM route candidates", C.green2),
            lightBand("07 rank", "profile, prompt, hybrid baselines", C.amber),
            lightBand("08 evaluate", "reconstruction + ranking metrics", C.coral),
          ],
        ),
        footer("Files: app/routing.py, app/profile.py, app/ranking.py, app/main.py, scripts/evaluate_route_candidate_baselines.py.", "#667A74"),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 6. GraphRAG interpretation
{
  const s = slide(C.night2);
  s.compose(
    grid(
      { width: fill, height: fill, columns: [fr(1.05), fr(0.95)], rows: [fr(1), auto], padding: { x: 92, y: 72 }, columnGap: 64 },
      [
        column({ width: fill, height: fill, gap: 24 }, [
          eyebrow("GraphRAG angle"),
          bigTitle("The graph is the memory. The language layer is the interface.", C.white, 60, 820),
          body("Road type, park proximity, turns, crossings, tunnels, lighting, temporal context, and profile weights become retrievable evidence. The route summary is not magic; it is a readable projection of the feature graph.", C.mist, 26, 760),
        ]),
        column({ width: fill, height: fill, gap: 24, justify: "center" }, [
          band("route nodes", "candidate geometry + coordinates", C.blue),
          band("feature edges", "OSM-derived attributes and tradeoffs", C.green),
          band("profile state", "dynamic preferences inferred from past signals", C.amber),
          band("evidence trail", "diagnostics attached to every confident answer", C.coral),
        ]),
        footer("Production implication: an agent can cite why a route was ranked, not merely generate a plausible route explanation."),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 7. Evaluation
{
  const s = slide(C.paper);
  s.compose(
    grid(
      { width: fill, height: fill, columns: [fr(0.82), fr(1.18)], rows: [auto, fr(1), auto], padding: { x: 84, y: 62 }, columnGap: 54, rowGap: 30 },
      [
        column({ width: fill, height: hug, gap: 14, columnSpan: 2 }, [
          eyebrow("evaluation", C.green2),
          bigTitle("Profile ranking gives the best graded signal, but the sample is still small.", C.ink, 52, 1360),
        ]),
        column({ width: fill, height: fill, gap: 26 }, [
          metric("0.727", "Profile NDCG@3", C.green2, 72),
          metric("0.630", "Profile path F1", C.green, 72),
          metric("8", "successful route-candidate queries", C.amber, 72),
          body("Useful signal, modest claim: profile-aware ranking improves several metrics over shortest distance, but this is not an external benchmark victory.", "#526D64", 23, 650),
        ]),
        chart({
          name: "ndcg-chart",
          chartType: "bar",
          width: fill,
          height: fill,
          config: {
            title: "NDCG@3 by method",
            categories: ["Random", "Shortest", "Profile", "Prompt", "Hybrid"],
            series: [{ name: "NDCG@3", values: [0.668, 0.69, 0.727, 0.673, 0.672] }],
          },
        }),
        footer("Source: data/route_candidate_baseline_comparison.json. Prompt text is synthetic and treated as an ablation."),
        shape({ width: fixed(1), height: fixed(1) }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 8. Production plan
{
  const s = slide(C.night);
  s.compose(
    grid(
      { width: fill, height: fill, columns: [fr(0.92), fr(1.08)], rows: [fr(1), auto], padding: { x: 92, y: 72 }, columnGap: 64 },
      [
        column({ width: fill, height: fill, gap: 26 }, [
          eyebrow("production plan"),
          bigTitle("Ship the decision engine, then earn the right to learn.", C.white, 62, 770),
          body("Before adding learned rankers, harden graph caching, replayable evaluation, route-diagnostic logging, and clean feedback collection.", C.mist, 26, 720),
        ]),
        column({ width: fill, height: fill, gap: 26, justify: "center" }, [
          band("cache", "precompute OSM graphs for property areas and common bounding boxes", C.green),
          band("observe", "log ranking inputs, top-k deltas, feature weights, and diagnostics", C.blue),
          band("govern", "separate pseudo-history, synthetic preferences, and clean labels", C.amber),
          band("learn", "introduce supervised rankers only after enough feedback exists", C.coral),
        ]),
        footer("Tradeoff posture for interview: product-minded shipping with research-grade caveat discipline.", "#9AB9AC"),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 9. Close
{
  const s = slide(C.ink);
  s.compose(
    layers({ width: fill, height: fill }, [
      image({ dataUrl: routeFieldDataUrl, contentType: "image/png", width: fill, height: fill, fit: "cover", alt: "Route field background" }),
      shape({ width: fill, height: fill, fill: "#10231FEE" }),
      grid(
        { width: fill, height: fill, columns: [fr(1), fr(0.92)], rows: [fr(1), auto], padding: { x: 94, y: 74 }, columnGap: 70 },
        [
          column({ width: fill, height: fill, gap: 24 }, [
            eyebrow("closing message"),
            bigTitle("I can build the AI platform layer between messy data and operational action.", C.white, 64, 850),
            rule({ width: fixed(190), stroke: C.green, weight: 7 }),
            body("That is the pitch: not just a model, not just a map, but a governed decision system with an evidence trail.", C.mist, 28, 760),
          ]),
          column({ width: fill, height: fill, gap: 26, justify: "center" }, [
            band("end-to-end", "data pipeline, API, ranker, evaluation, demo", C.green),
            band("systems judgment", "latency, caching, observability, deployment cost", C.blue),
            band("product translation", "investment, operations, resident experience, knowledge workflows", C.amber),
          ]),
          footer("Suggested walkthrough: problem -> product surface -> architecture -> GraphRAG memory -> evaluation -> production roadmap.", "#9AB9AC"),
        ],
      ),
    ]),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

const pptxPath = path.join(outputDir, "RouteGraphRAG_Aker_Product_Pitch_v2.pptx");
const pptxBlob = await PresentationFile.exportPptx(p);
await pptxBlob.save(pptxPath);

for (let i = 0; i < p.slides.count; i += 1) {
  const png = await p.slides.getItem(i).export({ format: "png" });
  fs.writeFileSync(path.join(previewDir, `slide-${String(i + 1).padStart(2, "0")}.png`), Buffer.from(await png.arrayBuffer()));
}

console.log(JSON.stringify({ pptxPath, previewDir, slideCount: p.slides.count }, null, 2));
