// Vercel Serverless Function (Node.js runtime)
// Endpoint: /api/pfp
// Usage: /api/pfp?url=<facebook-profile-url>&redirect=1

export default async function handler(req, res) {
  try {
    const { url, redirect } = req.query;
    if (!url) {
      res.status(400).json({ error: "Missing required query param: url" });
      return;
    }

    // 1) Parse and normalize the incoming URL
    let usernameOrId;
    try {
      const u = new URL(url);

      const path = u.pathname || "/";
      const cleanSegments = path.split("/").filter(Boolean);

      if (path.includes("/friends/")) {
        usernameOrId = u.searchParams.get("profile_id");
      } else if (path.includes("/groups/")) {
        // e.g. /groups/<something>/<username>...
        usernameOrId = cleanSegments[3];
      } else if (path.includes("/t/") && !path.includes("/e2ee/")) {
        // e.g. /t/<username>
        usernameOrId = cleanSegments[1];
      } else if (path === "/profile.php") {
        usernameOrId = u.searchParams.get("id");
      } else {
        // Regular profile like /zuck or /people/Name/123456...
        // If it's /people/.../ID, last segment could be numeric ID
        usernameOrId = cleanSegments[cleanSegments.length - 1] || "";
      }

      if (!usernameOrId) {
        res.status(400).json({ error: "Could not extract username/ID from URL." });
        return;
      }
    } catch {
      res.status(400).json({ error: "Invalid URL." });
      return;
    }

    // 2) If we already have a numeric ID, skip scraping
    let fbId = /^\d+$/.test(usernameOrId) ? usernameOrId : null;

    // 3) Otherwise fetch m.facebook.com/<username> to extract "userID"
    if (!fbId) {
      const mUrl = `https://m.facebook.com/${encodeURIComponent(usernameOrId)}`;
      const resp = await fetch(mUrl, {
        // lightweight headers; no cookie
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
          "Accept-Language": "en-US,en;q=0.9",
        },
      });

      const html = await resp.text();
      const match = html.match(/"userID":"(\d+)"/);
      if (!match) {
        return res.status(404).json({ error: "Could not extract Facebook Profile ID." });
      }
      fbId = match[1];
    }

    // 4) Build the Graph picture URL
    // IMPORTANT: do NOT hardcode tokens. Put your token in an env var if you use one.
    const token = process.env.FB_GRAPH_TOKEN; // optional
    const pictureBase = `https://graph.facebook.com/${fbId}/picture?width=5000`;
    const imageUrl = token ? `${pictureBase}&access_token=${encodeURIComponent(token)}` : pictureBase;

    // Optional caching to reduce re-hits
    res.setHeader("Cache-Control", "public, s-maxage=86400, stale-while-revalidate=604800");

    if (redirect === "1" || redirect === "true") {
      // 302 redirect to the image
      res.writeHead(302, { Location: imageUrl });
      res.end();
      return;
    }

    res.status(200).json({ id: fbId, imageUrl });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Internal Server Error" });
  }
}
