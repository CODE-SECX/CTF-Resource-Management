from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    session,
)
import json
import os
from datetime import datetime
import markdown
from collections import Counter
import difflib
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)
app.config["JSON_FILE"] = "resources.json"
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["ALLOWED_EXTENSIONS"] = {"pdf", "doc", "docx", "txt", "zip", "rar", "png", "jpg", "jpeg", "gif"}

# Create uploads directory if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# Load resources from JSON file
def load_resources():
    if os.path.exists(app.config["JSON_FILE"]):
        with open(app.config["JSON_FILE"], "r") as f:
            return json.load(f)
    return {"resources": []}


# Save resources to JSON file
def save_resources(data):
    with open(app.config["JSON_FILE"], "w") as f:
        json.dump(data, f, indent=4)


def get_similar_resources(resource, all_resources, limit=3):
    """Find similar resources based on tags and category"""
    similar = []
    for r in all_resources:
        if r["id"] != resource["id"]:
            # Calculate similarity score
            tag_similarity = len(set(resource["tags"]) & set(r["tags"])) / len(
                set(resource["tags"]) | set(r["tags"])
            )
            category_match = 1 if r["category"] == resource["category"] else 0
            score = (tag_similarity * 0.7) + (category_match * 0.3)

            if score > 0.2:  # Only include if similarity is significant
                similar.append((r, score))

    # Sort by similarity score and return top matches
    similar.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in similar[:limit]]


def get_popular_tags(limit=10):
    """Get most popular tags across all resources"""
    data = load_resources()
    all_tags = []
    for resource in data["resources"]:
        all_tags.extend(resource["tags"])
    return [tag for tag, count in Counter(all_tags).most_common(limit)]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


# Function to get categories
def get_categories():
    data = load_resources()
    if "categories" not in data:
        data["categories"] = [
            {"id": 1, "name": "Web Exploitation", "slug": "web", "icon": "fas fa-globe"},
            {"id": 2, "name": "Cryptography", "slug": "crypto", "icon": "fas fa-key"},
            {"id": 3, "name": "Reverse Engineering", "slug": "rev", "icon": "fas fa-microchip"},
            {"id": 4, "name": "Binary Exploitation", "slug": "pwn", "icon": "fas fa-bug"},
            {"id": 5, "name": "Forensics", "slug": "forensics", "icon": "fas fa-search"},
            {"id": 6, "name": "Miscellaneous", "slug": "misc", "icon": "fas fa-puzzle-piece"}
        ]
        save_resources(data)
    return data["categories"]


@app.route("/")
def index():
    data = load_resources()
    popular_tags = get_popular_tags()
    return render_template(
        "index.html", resources=data["resources"], popular_tags=popular_tags
    )


@app.route("/resource/<int:resource_id>")
def resource_details(resource_id):
    data = load_resources()
    for resource in data["resources"]:
        if resource["id"] == resource_id:
            # Convert markdown description to HTML if it exists
            if "description" in resource:
                resource["description_html"] = markdown.markdown(
                    resource["description"]
                )

            # Get similar resources
            similar_resources = get_similar_resources(resource, data["resources"])

            # Track view count
            if "views" not in resource:
                resource["views"] = 0
            resource["views"] += 1
            save_resources(data)

            return render_template(
                "resource_details.html",
                resource=resource,
                similar_resources=similar_resources,
            )
    flash("Resource not found")
    return redirect(url_for("index"))


@app.route("/api/resources")
def get_resources():
    data = load_resources()
    return jsonify(data["resources"])


@app.route("/add_resource", methods=["GET", "POST"])
def add_resource_page():
    """Route for the Add Resource page with TinyMCE integration"""
    if request.method == "POST":
        # Process form submission
        title = request.form.get("title")
        category = request.form.get("category")
        tags = [tag.strip() for tag in request.form.get("tags", "").split(",") if tag.strip()]
        url = request.form.get("url")
        description = request.form.get("description")
        
        # Validate required fields
        if not title or not category:
            flash("Title and category are required fields")
            return render_template("add_resource.html")
        
        # Handle file upload
        file_path = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                # Generate a secure filename with UUID to prevent duplicates
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)
                # Make the path relative to static for serving
                file_path = file_path.replace("static/", "", 1)
        
        # Create new resource
        data = load_resources()
        new_resource = {
            "id": len(data["resources"]) + 1,
            "name": title,
            "category": category,
            "tags": tags,
            "url": url,
            "description": description,
            "file_path": file_path,
            "date_added": datetime.now().isoformat(),
            "added_by": session.get("username", "Anonymous"),
            "rating": 0,
            "ratings_count": 0,
            "views": 0
        }
        
        data["resources"].append(new_resource)
        save_resources(data)
        
        flash("Resource added successfully!")
        return redirect(url_for("resource_details", resource_id=new_resource["id"]))
    
    # GET request - display the form
    categories = get_categories()
    return render_template("add_resource.html", categories=categories)


@app.route("/api/resources", methods=["POST"])
def add_resource_api():
    data = load_resources()
    
    # Check if the request is JSON or form data
    if request.is_json:
        new_resource = request.json
    else:
        # Handle form submissions from API clients
        new_resource = {
            "name": request.form.get("name"),
            "category": request.form.get("category"),
            "tags": request.form.get("tags", "").split(","),
            "url": request.form.get("url"),
            "description": request.form.get("description"),
        }
    
    new_resource["id"] = len(data["resources"]) + 1
    new_resource["date_added"] = datetime.now().isoformat()
    new_resource["added_by"] = "Anonymous"
    new_resource["rating"] = 0
    new_resource["ratings_count"] = 0
    new_resource["views"] = 0

    data["resources"].append(new_resource)
    save_resources(data)
    
    # Return JSON for API requests, redirect for form submissions
    if request.is_json:
        return jsonify(new_resource), 201
    else:
        flash("Resource added successfully!")
        return redirect(url_for("resource_details", resource_id=new_resource["id"]))


@app.route("/api/resources/<int:resource_id>/rate", methods=["POST"])
def rate_resource(resource_id):
    data = load_resources()
    rating = request.json.get("rating")

    for resource in data["resources"]:
        if resource["id"] == resource_id:
            resource["rating"] = (
                (resource["rating"] * resource["ratings_count"]) + rating
            ) / (resource["ratings_count"] + 1)
            resource["ratings_count"] += 1
            break

    save_resources(data)
    return jsonify({"message": "Rating updated successfully"})


@app.route("/api/tags/suggestions")
def get_tag_suggestions():
    query = request.args.get("q", "").lower()
    if not query:
        return jsonify([])

    data = load_resources()
    all_tags = set()
    for resource in data["resources"]:
        all_tags.update(resource["tags"])

    # Find matching tags using fuzzy matching
    matches = difflib.get_close_matches(query, all_tags, n=5, cutoff=0.3)
    return jsonify(matches)


@app.route("/api/analytics")
def get_analytics():
    data = load_resources()

    # Category distribution
    categories = Counter(r["category"] for r in data["resources"])

    # Popular tags
    all_tags = []
    for resource in data["resources"]:
        all_tags.extend(resource["tags"])
    popular_tags = Counter(all_tags).most_common(10)

    # Most viewed resources
    most_viewed = sorted(
        data["resources"], key=lambda x: x.get("views", 0), reverse=True
    )[:5]

    # Most rated resources
    most_rated = sorted(
        data["resources"], key=lambda x: x.get("ratings_count", 0), reverse=True
    )[:5]

    return jsonify(
        {
            "categories": dict(categories),
            "popular_tags": dict(popular_tags),
            "most_viewed": [
                {"id": r["id"], "name": r["name"], "views": r.get("views", 0)}
                for r in most_viewed
            ],
            "most_rated": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "rating": r["rating"],
                    "ratings_count": r.get("ratings_count", 0),
                }
                for r in most_rated
            ],
        }
    )


@app.route("/resource/<int:resource_id>/edit", methods=["GET", "POST"])
def edit_resource(resource_id):
    """Route for editing an existing resource"""
    data = load_resources()
    
    # Find the resource
    resource = None
    for r in data["resources"]:
        if r["id"] == resource_id:
            resource = r
            break
    
    if not resource:
        flash("Resource not found")
        return redirect(url_for("index"))
    
    if request.method == "POST":
        # Process form submission
        title = request.form.get("title")
        category = request.form.get("category")
        tags = [tag.strip() for tag in request.form.get("tags", "").split(",") if tag.strip()]
        url = request.form.get("url")
        description = request.form.get("description")
        
        # Validate required fields
        if not title or not category:
            flash("Title and category are required fields")
            return render_template("edit_resource.html", resource=resource)
        
        # Handle file upload
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            if allowed_file(file.filename):
                # Delete old file if exists
                if "file_path" in resource and resource["file_path"]:
                    old_file_path = os.path.join("static", resource["file_path"])
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                
                # Generate a secure filename with UUID to prevent duplicates
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)
                # Make the path relative to static for serving
                resource["file_path"] = file_path.replace("static/", "", 1)
        
        # Update resource
        resource["name"] = title
        resource["category"] = category
        resource["tags"] = tags
        resource["url"] = url
        resource["description"] = description
        resource["date_updated"] = datetime.now().isoformat()
        
        save_resources(data)
        
        flash("Resource updated successfully!")
        return redirect(url_for("resource_details", resource_id=resource_id))
    
    # GET request - display the form with pre-filled data
    categories = get_categories() 
    return render_template("edit_resource.html", resource=resource, categories=categories)


@app.route("/resource/<int:resource_id>/delete", methods=["POST"])
def delete_resource(resource_id):
    """Route for deleting a resource"""
    data = load_resources()
    
    # Find the resource
    resource_index = None
    for i, r in enumerate(data["resources"]):
        if r["id"] == resource_id:
            resource_index = i
            resource = r
            break
    
    if resource_index is None:
        flash("Resource not found")
        return redirect(url_for("index"))
    
    # Delete associated file if exists
    if "file_path" in resource and resource["file_path"]:
        file_path = os.path.join("static", resource["file_path"])
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Remove the resource
    data["resources"].pop(resource_index)
    save_resources(data)
    
    flash("Resource deleted successfully")
    return redirect(url_for("index"))


@app.route("/categories", methods=["GET", "POST"])
def category_management():
    """Route for managing categories"""
    data = load_resources()
    categories = get_categories()
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            # Add new category
            name = request.form.get("name")
            slug = request.form.get("slug", "").lower()
            icon = request.form.get("icon", "fas fa-folder")
            
            # Validate inputs
            if not name or not slug:
                flash("Category name and slug are required")
                return redirect(url_for("category_management"))
            
            # Check for duplicate slugs
            if any(c["slug"] == slug for c in categories):
                flash("A category with this slug already exists")
                return redirect(url_for("category_management"))
            
            # Add new category
            new_id = max([c["id"] for c in categories], default=0) + 1
            categories.append({
                "id": new_id,
                "name": name,
                "slug": slug,
                "icon": icon
            })
            
            data["categories"] = categories
            save_resources(data)
            flash("Category added successfully")
            
        elif action == "edit":
            # Edit existing category
            category_id = int(request.form.get("category_id"))
            name = request.form.get("name")
            slug = request.form.get("slug", "").lower()
            icon = request.form.get("icon")
            
            # Validate inputs
            if not name or not slug:
                flash("Category name and slug are required")
                return redirect(url_for("category_management"))
            
            # Update category
            for category in categories:
                if category["id"] == category_id:
                    category["name"] = name
                    category["slug"] = slug
                    category["icon"] = icon
                    break
            
            data["categories"] = categories
            save_resources(data)
            flash("Category updated successfully")
            
        elif action == "delete":
            # Delete category
            category_id = int(request.form.get("category_id"))
            
            # Check if category is in use
            resources_with_category = [r for r in data["resources"] if r["category"] == next((c["slug"] for c in categories if c["id"] == category_id), None)]
            if resources_with_category:
                flash(f"Cannot delete category because it is used by {len(resources_with_category)} resources")
                return redirect(url_for("category_management"))
            
            # Remove category
            data["categories"] = [c for c in categories if c["id"] != category_id]
            save_resources(data)
            flash("Category deleted successfully")
        
        return redirect(url_for("category_management"))
    
    return render_template("categories.html", categories=categories)


@app.route("/favorites")
def favorites_page():
    """Route for viewing favorited resources"""
    data = load_resources()
    popular_tags = get_popular_tags()
    return render_template("favorites.html", resources=data["resources"], popular_tags=popular_tags)


@app.route("/browse")
def content_index():
    """Route for the content index page with organized category and tag browsing"""
    data = load_resources()
    resources = data["resources"]
    categories = get_categories()
    
    # Get all unique tags across resources
    all_tags = set()
    for resource in resources:
        all_tags.update(resource["tags"])
    
    # Sort tags alphabetically
    sorted_tags = sorted(list(all_tags))
    
    # Group resources by category
    resources_by_category = {}
    for category in categories:
        category_resources = [r for r in resources if r["category"] == category["slug"]]
        resources_by_category[category["slug"]] = category_resources
    
    return render_template(
        "content_index.html", 
        categories=categories,
        resources_by_category=resources_by_category,
        all_tags=sorted_tags
    )


if __name__ == "__main__":
    app.run(debug=True)
