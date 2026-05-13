import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const artifactPath = require.resolve("@oai/artifact-tool");
const artifact = await import(pathToFileURL(artifactPath).href);

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
} = artifact;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workspace = path.resolve(__dirname, "..");
const outputDir = path.join(workspace, "output");
const scratchDir = path.join(workspace, "scratch");
const previewDir = path.join(scratchDir, "previews");
const assetDir = path.join(__dirname, "assets");
const routeFieldDataUrl = `data:image/png;base64,${fs.readFileSync(path.join(assetDir, "route_trace_field.png")).toString("base64")}`;

fs.mkdirSync(outputDir, { recursive: true });
fs.mkdirSync(previewDir, { recursive: true });

const W = 1920;
const H = 1080;

const C = {
  ink: "#10231F",
  muted: "#58706A",
  soft: "#DCE9E2",
  paper: "#F7FAF6",
  field: "#0F1720",
  green: "#43D08A",
  moss: "#0F766E",
  amber: "#F59E0B",
  coral: "#FF6B4A",
  blue: "#2D6CDF",
  white: "#FFFFFF",
};

const font = "Aptos";
const mono = "Cascadia Mono";

const presentation = Presentation.create({
  slideSize: { width: W, height: H },
});

function addSlide(bg = C.paper) {
  const s = presentation.slides.add();
  s.compose(
    layers({ name: "background", width: fill, height: fill }, [
      shape({ name: "bg", width: fill, height: fill, fill: bg }),
    ]),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
  return s;
}

function titleStack(title, subtitle, source = "") {
  return column({ name: "title-stack", width: fill, height: hug, gap: 14 }, [
    text(title, {
      name: "slide-title",
      width: wrap(1320),
      height: hug,
      style: { fontFace: font, fontSize: 54, bold: true, color: C.ink },
    }),
    subtitle
      ? text(subtitle, {
          name: "slide-subtitle",
          width: wrap(1200),
          height: hug,
          style: { fontFace: font, fontSize: 24, color: C.muted },
        })
      : shape({ width: fixed(1), height: fixed(1) }),
    rule({ name: "title-rule", width: fixed(160), stroke: C.green, weight: 5 }),
    source
      ? text(source, {
          name: "source",
          width: wrap(1180),
          height: hug,
          style: { fontFace: font, fontSize: 12, color: "#78918A" },
        })
      : shape({ width: fixed(1), height: fixed(1) }),
  ]);
}

function smallLabel(value, color = C.moss) {
  return text(value, {
    name: `label-${value.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
    width: fill,
    height: hug,
    style: { fontFace: font, fontSize: 17, bold: true, color },
  });
}

function openMetric(value, label, accent = C.green) {
  return column({ name: `metric-${label}`, width: fill, height: hug, gap: 4 }, [
    text(value, {
      name: `metric-value-${label}`,
      width: fill,
      height: hug,
      style: { fontFace: font, fontSize: 56, bold: true, color: accent },
    }),
    text(label, {
      name: `metric-label-${label}`,
      width: fill,
      height: hug,
      style: { fontFace: font, fontSize: 18, color: C.muted },
    }),
  ]);
}

function processNode(kicker, body, accent = C.green) {
  return panel(
    {
      name: `node-${kicker}`,
      width: fill,
      height: fill,
      padding: { x: 24, y: 22 },
      fill: "#FFFFFF",
      line: { fill: "#D8E7E0", width: 1 },
      borderRadius: 8,
    },
    column({ width: fill, height: hug, gap: 10 }, [
      smallLabel(kicker, accent),
      text(body, {
        name: `node-copy-${kicker}`,
        width: fill,
        height: hug,
        style: { fontFace: font, fontSize: 22, bold: true, color: C.ink },
      }),
    ]),
  );
}

function footer(textValue) {
  return text(textValue, {
    name: "footer",
    width: fill,
    height: hug,
    style: { fontFace: font, fontSize: 13, color: "#7A8E88" },
  });
}

// 1. Cover
{
  const s = addSlide(C.field);
  s.compose(
    layers({ width: fill, height: fill }, [
      image({
        name: "route-field",
        dataUrl: routeFieldDataUrl,
        contentType: "image/png",
        width: fill,
        height: fill,
        fit: "cover",
        alt: "Reconstructed OSM route field",
      }),
      shape({ name: "cover-scrim", width: fill, height: fill, fill: "#0F1720CC" }),
      grid(
        {
          name: "cover-root",
          width: fill,
          height: fill,
          columns: [fr(1.18), fr(0.52)],
          rows: [fr(1), auto],
          padding: { x: 92, y: 76 },
        },
        [
          column({ width: fill, height: fill, gap: 28 }, [
            text("Route\nGraphRAG", {
              name: "cover-title",
              width: wrap(1120),
              height: hug,
              style: { fontFace: font, fontSize: 76, bold: true, color: C.white },
            }),
            text("Preference-aware route ranking from noisy geospatial signals", {
              name: "cover-subtitle",
              width: wrap(1080),
              height: hug,
              style: { fontFace: font, fontSize: 28, color: "#CFE7DC" },
            }),
            rule({ width: fixed(220), stroke: C.green, weight: 7 }),
            text("Technical deep dive for Aker AI Platform Engineering", {
              name: "cover-context",
              width: wrap(820),
              height: hug,
              style: { fontFace: font, fontSize: 24, color: "#97B5AA" },
            }),
          ]),
          shape({ width: fill, height: fill }),
          text("Built around FastAPI, OSMnx, dynamic profiles, SBERT ranking, and explicit reconstruction diagnostics.", {
            name: "cover-bottom",
            columnSpan: 2,
            width: wrap(1120),
            height: hug,
            style: { fontFace: font, fontSize: 21, color: "#BBD6CA" },
          }),
        ],
      ),
    ]),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 2. Why Aker cares
{
  const s = addSlide();
  s.compose(
    grid(
      {
        name: "aker-fit-root",
        width: fill,
        height: fill,
        columns: [fr(0.95), fr(1.05)],
        rows: [auto, fr(1), auto],
        padding: { x: 86, y: 66 },
        columnGap: 64,
        rowGap: 34,
      },
      [
        titleStack(
          "Aker's platform thesis is exactly this problem class",
          "Turn messy operational data into internal tools, knowledge, and agents that drive real decisions.",
          "Source: Aker AI Platform public site and LinkedIn hiring post, accessed May 2026.",
        ),
        shape({ width: fill, height: fixed(1) }),
        column({ width: fill, height: fill, gap: 28 }, [
          text("The product pitch", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 26, bold: true, color: C.moss },
          }),
          text("RouteGraphRAG is a pattern for Aker's internal AI platform: ingest imperfect operational traces, build an explainable representation, rank options, and show the uncertainty before anyone trusts the output.", {
            name: "pitch-copy",
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 35, bold: true, color: C.ink },
          }),
        ]),
        grid(
          {
            name: "aker-operators",
            width: fill,
            height: fill,
            columns: [fr(1), fr(1)],
            rows: [fr(1), fr(1)],
            gap: 18,
          },
          [
            processNode("INVEST", "Site context, trade areas, walkability, asset diligence", C.blue),
            processNode("OPERATE", "Field movement patterns, service routing, inspection planning", C.green),
            processNode("SERVE", "Resident-facing route guidance and neighborhood intelligence", C.amber),
            processNode("KNOW", "A knowledge layer that explains why a route was ranked", C.coral),
          ],
        ),
        footer("Aker framing: agents, tools, workflows, knowledge, and production AI systems for real estate operations."),
        shape({ width: fill, height: fixed(1) }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 3. Product surface
{
  const s = addSlide();
  s.compose(
    grid(
      {
        width: fill,
        height: fill,
        columns: [fr(0.85), fr(1.15)],
        rows: [auto, fr(1), auto],
        padding: { x: 86, y: 66 },
        columnGap: 58,
        rowGap: 34,
      },
      [
        titleStack("The product ranks routes the way a person actually asks", "A natural-language preference, a dynamic profile, and OSM features combine into explainable route candidates."),
        shape({ width: fill, height: fixed(1) }),
        column({ width: fill, height: fill, gap: 24 }, [
          text("Example request", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 23, bold: true, color: C.moss },
          }),
          panel(
            { padding: { x: 30, y: 28 }, fill: "#10231F", borderRadius: 8, width: fill, height: hug },
            column({ width: fill, height: hug, gap: 15 }, [
              text("Prefer quieter walking routes near parks and away from major roads.", {
                name: "request-text",
                width: fill,
                height: hug,
                style: { fontFace: font, fontSize: 29, bold: true, color: C.white },
              }),
              text("origin + destination + timestamp + user_id + ranking_mode=hybrid", {
                width: fill,
                height: hug,
                style: { fontFace: mono, fontSize: 17, color: "#A7DCC6" },
              }),
            ]),
          ),
          row({ width: fill, height: hug, gap: 28 }, [
            openMetric("5", "ranked candidates", C.moss),
            openMetric("3", "ranking modes", C.amber),
          ]),
        ]),
        grid(
          {
            name: "product-flow",
            width: fill,
            height: fill,
            columns: [fr(1), fixed(44), fr(1), fixed(44), fr(1)],
            rows: [fr(1)],
            columnGap: 10,
          },
          [
            processNode("INPUT", "Preference text plus route context", C.blue),
            text(">", { width: fill, height: hug, style: { fontFace: font, fontSize: 46, bold: true, color: C.green } }),
            processNode("RANK", "Profile score + prompt/SBERT score", C.green),
            text(">", { width: fill, height: hug, style: { fontFace: font, fontSize: 46, bold: true, color: C.green } }),
            processNode("EXPLAIN", "Feature summary, scores, coordinates", C.amber),
          ],
        ),
        footer("Backend endpoint: /rank-routes. Modes: prompt, profile, hybrid."),
        shape({ width: fill, height: fixed(1) }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 4. Route-field visual
{
  const s = addSlide(C.field);
  s.compose(
    grid(
      {
        width: fill,
        height: fill,
        columns: [fr(0.85), fr(1.15)],
        rows: [fr(1), auto],
        padding: { x: 76, y: 58 },
        columnGap: 52,
        rowGap: 24,
      },
      [
        column({ width: fill, height: fill, gap: 24 }, [
          text("The hard part is not drawing a route. It is deciding which route deserves rank 1.", {
            name: "visual-claim",
            width: wrap(650),
            height: hug,
            style: { fontFace: font, fontSize: 54, bold: true, color: C.white },
          }),
          rule({ width: fixed(180), stroke: C.green, weight: 6 }),
          text("This field view uses actual OSM pseudo-history records: raw public GPS samples are reconstructed onto OSM walking geometry, then converted into route features.", {
            name: "visual-copy",
            width: wrap(650),
            height: hug,
            style: { fontFace: font, fontSize: 25, color: "#C8DED5" },
          }),
        ]),
      image({
        name: "route-field-image",
        dataUrl: routeFieldDataUrl,
        contentType: "image/png",
        width: fill,
        height: fill,
          fit: "contain",
          alt: "Route trace field",
          borderRadius: 8,
        }),
        text("Important wording: OSM-derived historical movement signals, not clean per-user history.", {
          name: "visual-caveat",
          columnSpan: 2,
          width: fill,
          height: hug,
          style: { fontFace: font, fontSize: 18, color: "#91B5A7" },
        }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 5. Architecture
{
  const s = addSlide();
  s.compose(
    grid(
      {
        width: fill,
        height: fill,
        columns: [fr(1)],
        rows: [auto, fr(1), auto],
        padding: { x: 80, y: 62 },
        rowGap: 38,
      },
      [
        titleStack("System architecture: one shared route representation", "Every stage produces or consumes the same route feature object, which keeps ranking explainable and testable."),
        grid(
          {
            name: "architecture-grid",
            width: fill,
            height: fill,
            columns: [fr(1), fixed(30), fr(1), fixed(30), fr(1), fixed(30), fr(1)],
            rows: [fr(1), fr(1)],
            gap: 18,
          },
          [
            processNode("1. PROBE", "OSM public GPS trackpoints in target bounding box", C.blue),
            text(">", { width: fill, height: hug, style: { fontFace: font, fontSize: 32, bold: true, color: C.green } }),
            processNode("2. SEGMENT", "Split by time gaps, spatial jumps, useful movement filters", C.green),
            text(">", { width: fill, height: hug, style: { fontFace: font, fontSize: 32, bold: true, color: C.green } }),
            processNode("3. MATCH", "Nearest OSM nodes plus shortest-path stitching", C.amber),
            text(">", { width: fill, height: hug, style: { fontFace: font, fontSize: 32, bold: true, color: C.green } }),
            processNode("4. FEATURES", "Distance, road mix, parks, turns, lighting, crossings", C.coral),
            shape({ width: fill, height: fixed(1) }),
            text(" ", { width: fill, height: hug, style: { fontSize: 1, color: C.paper } }),
            processNode("5. PROFILE", "Contextual weights from prior pseudo-history records", C.blue),
            text(">", { width: fill, height: hug, style: { fontFace: font, fontSize: 32, bold: true, color: C.green } }),
            processNode("6. CANDIDATES", "Diverse OSM routes under length, scenic, safe, simple costs", C.green),
            text(">", { width: fill, height: hug, style: { fontFace: font, fontSize: 32, bold: true, color: C.green } }),
            processNode("7. RANK", "Random, shortest, profile, prompt/SBERT, hybrid", C.amber),
          ],
        ),
        footer("Key design choice: keep model-facing text and numerical feature scoring traceable to the same OSM-derived representation."),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 6. Knowledge / RAG angle
{
  const s = addSlide();
  s.compose(
    grid(
      {
        width: fill,
        height: fill,
        columns: [fr(1.05), fr(0.95)],
        rows: [auto, fr(1), auto],
        padding: { x: 84, y: 64 },
        columnGap: 56,
        rowGap: 30,
      },
      [
        titleStack("The GraphRAG idea is a routing memory, not a chatbot wrapper", "Route facts become inspectable nodes, weights, summaries, and retrieval context."),
        shape({ width: fill, height: fixed(1) }),
        column({ width: fill, height: fill, gap: 24 }, [
          text("Representation", { width: fill, height: hug, style: { fontFace: font, fontSize: 24, bold: true, color: C.moss } }),
          text("Route candidates are ranked by a structured feature graph: road-type mix, park proximity, lighting, crossings, tunnels, turns, temporal context, and profile weights.", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 34, bold: true, color: C.ink },
          }),
          text("The LLM/SBERT layer only sees route summaries derived from the same features, so natural language preferences remain auditable.", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 23, color: C.muted },
          }),
        ]),
        grid(
          {
            name: "kg-grid",
            width: fill,
            height: fill,
            columns: [fr(1), fr(1)],
            rows: [fr(1), fr(1), fr(1)],
            gap: 16,
          },
          [
            processNode("ROUTE", "candidate geometry + coordinates", C.blue),
            processNode("CONTEXT", "weekday, time bucket, season, rush hour", C.amber),
            processNode("FEATURES", "interpretable OSM-derived attributes", C.green),
            processNode("PROFILE", "dynamic weights from historical signals", C.coral),
            processNode("TEXT", "summary used for semantic ranking", C.moss),
            processNode("EVIDENCE", "diagnostics attached to each claim", C.blue),
          ],
        ),
        footer("Production implication: retrieval can cite route features and data quality, not just emit a plausible answer."),
        shape({ width: fill, height: fixed(1) }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 7. Evaluation
{
  const s = addSlide();
  s.compose(
    grid(
      {
        width: fill,
        height: fill,
        columns: [fr(0.82), fr(1.18)],
        rows: [auto, fr(1), auto],
        padding: { x: 84, y: 62 },
        columnGap: 54,
        rowGap: 30,
      },
      [
        titleStack("Evaluation says profile ranking is useful, but not yet a victory lap", "The profile baseline improves the strongest graded/path signal over shortest distance on a small, noisy OSM pseudo-history run."),
        shape({ width: fill, height: fixed(1) }),
        column({ width: fill, height: fill, gap: 28 }, [
          openMetric("0.727", "Profile NDCG@3", C.moss),
          openMetric("0.630", "Profile path F1", C.green),
          openMetric("8", "successful route-candidate queries", C.amber),
          text("Interpretation: promising system behavior, not a claim that it beats prior personalized-routing research.", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 22, color: C.muted },
          }),
        ]),
        chart({
          name: "evaluation-chart",
          chartType: "bar",
          width: fill,
          height: fill,
          config: {
            title: "NDCG@3 by method",
            categories: ["Random", "Shortest", "Profile", "Prompt", "Hybrid"],
            series: [{ name: "NDCG@3", values: [0.668, 0.69, 0.727, 0.673, 0.672] }],
          },
        }),
        footer("Source: data/route_candidate_baseline_comparison.json. Prompt and hybrid use synthetic preference text as ablation only."),
        shape({ width: fill, height: fixed(1) }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 8. Data quality
{
  const s = addSlide();
  s.compose(
    grid(
      {
        width: fill,
        height: fill,
        columns: [fr(1), fr(1)],
        rows: [auto, fr(1), auto],
        padding: { x: 84, y: 62 },
        columnGap: 54,
        rowGap: 34,
      },
      [
        titleStack("The strongest engineering signal is the caveat handling", "The system separates reconstruction quality from ranking quality instead of hiding data uncertainty."),
        shape({ width: fill, height: fixed(1) }),
        grid({ width: fill, height: fill, columns: [fr(1), fr(1)], rows: [fr(1), fr(1)], gap: 22 }, [
          processNode("25,000", "timestamped OSM trackpoints probed", C.blue),
          processNode("11", "useful pseudo-segments found", C.green),
          processNode("100%", "map-match success rate", C.amber),
          processNode("6.99 m", "median GPS-to-route distance", C.coral),
        ]),
        column({ width: fill, height: fill, gap: 24 }, [
          text("Passes exploratory gate", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 42, bold: true, color: C.moss },
          }),
          text("Fails strict gate because median route-distance ratio is 2.37, above the strict target range. That means the route may stay close to points while still overbuilding path length.", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 30, bold: true, color: C.ink },
          }),
          text("Production move: promote confidence and reconstruction diagnostics into the API response, evaluation dashboards, and human review loop.", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 22, color: C.muted },
          }),
        ]),
        footer("Source: data/threshold_sensitivity.json and docs/THRESHOLD_SENSITIVITY_STUDY.md."),
        shape({ width: fill, height: fixed(1) }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 9. Production surface
{
  const s = addSlide();
  s.compose(
    grid(
      {
        width: fill,
        height: fill,
        columns: [fr(1), fr(1)],
        rows: [auto, fr(1), auto],
        padding: { x: 84, y: 62 },
        columnGap: 54,
        rowGap: 32,
      },
      [
        titleStack("What I would productionize first", "The existing backend is enough to show the product; the next layer is reliability, observability, and evaluation discipline."),
        shape({ width: fill, height: fixed(1) }),
        column({ width: fill, height: fill, gap: 20 }, [
          processNode("API CONTRACT", "Keep route features, component scores, summary, coordinates, and profile summary in every response.", C.blue),
          processNode("CACHE + COST", "Cache OSM graph builds by bounding box and precompute common property-area graphs.", C.green),
          processNode("EVAL HARNESS", "Run random, shortest, profile, prompt, hybrid on the same candidate pool after every ranking change.", C.amber),
        ]),
        column({ width: fill, height: fill, gap: 20 }, [
          processNode("OBSERVABILITY", "Log ranking inputs, top-k deltas, feature weights, and diagnostics for replay.", C.coral),
          processNode("DATA GOVERNANCE", "Label pseudo-history, synthetic preference text, and clean user-labeled data separately.", C.moss),
          processNode("HUMAN LOOP", "Capture route accept/reject feedback before introducing learned rankers.", C.blue),
        ]),
        footer("Tradeoff posture: ship the demo, but do not let model confidence outrun data provenance."),
        shape({ width: fill, height: fixed(1) }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// 10. Close
{
  const s = addSlide(C.ink);
  s.compose(
    grid(
      {
        width: fill,
        height: fill,
        columns: [fr(0.95), fr(1.05)],
        rows: [fr(1), auto],
        padding: { x: 92, y: 76 },
        columnGap: 60,
        rowGap: 30,
      },
      [
        column({ width: fill, height: fill, gap: 28 }, [
          text("Why this fits Aker", {
            width: fill,
            height: hug,
            style: { fontFace: font, fontSize: 72, bold: true, color: C.white },
          }),
          rule({ width: fixed(190), stroke: C.green, weight: 7 }),
          text("It is an AI platform pattern: connect data, encode domain judgment, rank operational options, expose uncertainty, and make the system better every sprint.", {
            width: wrap(740),
            height: hug,
            style: { fontFace: font, fontSize: 33, color: "#CBE4D9" },
          }),
        ]),
        column({ width: fill, height: fill, gap: 26 }, [
          processNode("I can build end-to-end", "FastAPI service, data pipeline, model/ranker, evaluation artifacts, and demo surface.", C.green),
          processNode("I know where the risk is", "Data quality, map matching, synthetic labels, overclaiming, and deployment cost.", C.amber),
          processNode("I can translate to Aker", "Property operations, investment diligence, resident experience, and internal knowledge workflows.", C.blue),
        ]),
        text("Round 1 discussion path: product problem -> architecture -> scoring tradeoffs -> evaluation -> production roadmap.", {
          columnSpan: 2,
          width: fill,
          height: hug,
          style: { fontFace: font, fontSize: 20, color: "#9FC2B3" },
        }),
      ],
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

const pptxBlob = await PresentationFile.exportPptx(presentation);
const pptxPath = path.join(outputDir, "RouteGraphRAG_Aker_Product_Pitch.pptx");
await pptxBlob.save(pptxPath);

for (let i = 0; i < presentation.slides.count; i += 1) {
  const slide = presentation.slides.getItem(i);
  const png = await slide.export({ format: "png" });
  fs.writeFileSync(
    path.join(previewDir, `slide-${String(i + 1).padStart(2, "0")}.png`),
    Buffer.from(await png.arrayBuffer()),
  );
  const layout = await slide.export({ format: "layout" });
  fs.writeFileSync(path.join(scratchDir, `slide-${String(i + 1).padStart(2, "0")}.layout.json`), JSON.stringify(layout, null, 2));
}

console.log(JSON.stringify({ pptxPath, previewDir, slideCount: presentation.slides.count }, null, 2));
process.exit(0);
