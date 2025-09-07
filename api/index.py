import os
import re
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # Vercel routes requests to this app, but the user is likely looking for the API endpoint.
    # We can provide a helpful message.
    return jsonify({
        "message": "Welcome to the Facebook PFP API!",
        "usage": "/api/pfp?url=<facebook-profile-url>&redirect=1"
    }), 200


@app.route('/api/pfp')
def get_pfp():
    try:
        url = request.args.get('url')
        should_redirect = request.args.get('redirect') in ['1', 'true']

        if not url:
            return jsonify({"error": "Missing required query param: url"}), 400

        # 1) Parse and normalize the incoming URL
        username_or_id = None
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path or "/"
            clean_segments = [segment for segment in path.split('/') if segment]
            query_params = parse_qs(parsed_url.query)

            if "/friends/" in path:
                username_or_id = query_params.get("profile_id", [None])[0]
            elif "/groups/" in path and len(clean_segments) > 3:
                username_or_id = clean_segments[3]
            elif "/t/" in path and "/e2ee/" not in path:
                username_or_id = clean_segments[1]
            elif path == "/profile.php":
                username_or_id = query_params.get("id", [None])[0]
            elif clean_segments:
                username_or_id = clean_segments[-1]

            if not username_or_id:
                return jsonify({"error": "Could not extract username/ID from URL."}), 400

        except Exception:
            return jsonify({"error": "Invalid URL."}), 400

        # 2) If we already have a numeric ID, skip scraping
        fb_id = username_or_id if username_or_id.isdigit() else None

        # 3) Otherwise fetch m.facebook.com/<username> to extract "userID"
        if not fb_id:
            import requests
            m_url = f"https://m.facebook.com/{username_or_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            
            resp = requests.get(m_url, headers=headers)
            resp.raise_for_status() # Will raise an exception for 4xx/5xx status codes
            
            html = resp.text
            match = re.search(r'"userID":"(\d+)"', html)
            
            if not match:
                return jsonify({"error": "Could not extract Facebook Profile ID."}), 404
            
            fb_id = match.group(1)

        # 4) Build the Graph picture URL
        token = os.environ.get('FB_GRAPH_TOKEN')
        picture_base = f"https://graph.facebook.com/{fb_id}/picture?width=5000"
        image_url = f"{picture_base}&access_token={token}" if token else picture_base

        # Optional caching
        headers = {
            "Cache-Control": "public, s-maxage=86400, stale-while-revalidate=604800"
        }

        if should_redirect:
            return redirect(image_url, code=302)

        return jsonify({"id": fb_id, "imageUrl": image_url}), 200, headers

    except Exception as e:
        print(f"Internal Server Error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

if __name__ == "__main__":
    # For local development testing
    app.run(debug=True)
