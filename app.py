from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    Response,
)
import json
import os
import sys
from datetime import datetime
import markdown
from collections import Counter
import difflib
from werkzeug.utils import secure_filename
import uuid
import notes
import io
import html2text

# Configure pdfkit with path to wkhtmltopdf if available
try:
    import pdfkit
    
    # Check if we're on Windows
    if sys.platform.startswith('win'):
        # Common install locations for wkhtmltopdf on Windows
        potential_paths = [
            r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',
            r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
            r'C:\wkhtmltopdf\bin\wkhtmltopdf.exe',
            r'C:\wkhtmltopdf\wkhtmltopdf.exe',
            r'C:\Program Files\wkhtmltopdf\wkhtmltopdf.exe',
        ]
        
        # Try to find wkhtmltopdf executable
        wkhtmltopdf_path = None
        for path in potential_paths:
            print(f"Checking for wkhtmltopdf at: {path}")
            if os.path.exists(path):
                wkhtmltopdf_path = path
                print(f"Found wkhtmltopdf at: {path}")
                break
        
        # Configure pdfkit with the path if found
        if wkhtmltopdf_path:
            pdfkit_config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        else:
            print("wkhtmltopdf not found in common locations")
            pdfkit_config = None
    else:
        # For Linux/Mac, let pdfkit find wkhtmltopdf in PATH
        print("Non-Windows system, looking for wkhtmltopdf in PATH")
        pdfkit_config = None
        
except ImportError:
    pdfkit = None
    pdfkit_config = None

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)
app.config["JSON_FILE"] = "resources.json"
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["ALLOWED_EXTENSIONS"] = {"pdf", "doc", "docx", "txt", "zip", "rar", "png", "jpg", "jpeg", "gif"}

# Create uploads directory if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Add custom filters for template rendering - REGISTER ALL FILTERS HERE BEFORE ROUTES
@app.template_filter('datetime')
def format_datetime(value):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%b %d, %Y, %H:%M")
    except (ValueError, TypeError):
        return value

@app.template_filter('now')
def _jinja2_filter_now():
    return datetime.now()
    
@app.template_filter('parse_date')
def _jinja2_filter_parse_date(date_string):
    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except:
        return datetime.now()


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


# Function to get learning categories
def get_learning_categories():
    data = load_resources()
    if "learning_categories" not in data:
        data["learning_categories"] = [
            {"id": 1, "name": "Introduction to CTF", "slug": "intro", "icon": "fas fa-flag"},
            {"id": 2, "name": "Web Security", "slug": "web-security", "icon": "fas fa-spider"},
            {"id": 3, "name": "Cryptography Basics", "slug": "crypto-basics", "icon": "fas fa-lock"},
            {"id": 4, "name": "Binary Analysis", "slug": "binary", "icon": "fas fa-microchip"},
            {"id": 5, "name": "Forensics Techniques", "slug": "forensics-tech", "icon": "fas fa-search"},
            {"id": 6, "name": "OSINT", "slug": "osint", "icon": "fas fa-eye"}
        ]
        save_resources(data)
    
    return data["learning_categories"]

def get_all_learning_categories():
    return get_learning_categories()


# Process HTML content
def process_description(description):
    """
    Process description content from TinyMCE editor.
    - If it's HTML (from TinyMCE), return it directly for safe display
    - If it's plain text or markdown, convert to HTML
    """
    if not description:
        return ""
    
    # If content already appears to be HTML (common indicators)
    if description.strip().startswith('<') and ('</p>' in description or '</div>' in description or '</h' in description):
        return description
    else:
        # Convert markdown to HTML
        return markdown.markdown(description)


@app.route("/")
def index():
    """Main landing page with overview of all sections"""
    return render_template("index.html")

@app.route("/resources")
def resources_page():
    """Dedicated page for browsing CTF resources"""
    data = load_resources()
    popular_tags = get_popular_tags()
    categories = get_categories()
    return render_template(
        "resources.html", resources=data["resources"], popular_tags=popular_tags, categories=categories
    )


@app.route("/resource/<int:resource_id>")
def resource_details(resource_id):
    data = load_resources()
    for resource in data["resources"]:
        if resource["id"] == resource_id:
            # Process the description for display
            if "description" in resource:
                resource["description_html"] = process_description(resource["description"])

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
            "description_html": process_description(description),
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
    
    # Process description HTML
    if "description" in new_resource:
        new_resource["description_html"] = process_description(new_resource["description"])
        
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
        resource["description_html"] = process_description(description)
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


# Data access functions for Learning resources
def get_all_learning_resources():
    data = load_resources()
    if "learning_resources" not in data:
        data["learning_resources"] = []
        save_resources(data)
    return data["learning_resources"]

def get_learning_by_id(learning_id):
    data = load_resources()
    for learning in data.get("learning_resources", []):
        if learning["id"] == learning_id:
            return learning
    return None

def add_learning_item(title, description, url, difficulty, category_ids):
    data = load_resources()
    
    # Initialize learning_resources if it doesn't exist
    if "learning_resources" not in data:
        data["learning_resources"] = []
    
    # Get a new ID for the learning resource
    learning_id = 1
    if data["learning_resources"]:
        learning_id = max([r["id"] for r in data["learning_resources"]]) + 1
    
    # Create the new learning resource
    new_learning = {
        "id": learning_id,
        "title": title,
        "description": description,
        "url": url,
        "difficulty": difficulty,
        "category_ids": [int(cat_id) for cat_id in category_ids],
        "date_added": datetime.now().isoformat(),
        "added_by": session.get("username", "Anonymous"),
        "views": 0,
        "completed_by": 0
    }
    
    data["learning_resources"].append(new_learning)
    save_resources(data)
    return learning_id

def update_learning(learning_id, title, description, url, difficulty, category_ids):
    data = load_resources()
    for learning in data.get("learning_resources", []):
        if learning["id"] == learning_id:
            learning["title"] = title
            learning["description"] = description
            learning["url"] = url
            learning["difficulty"] = difficulty
            learning["category_ids"] = [int(cat_id) for cat_id in category_ids]
            learning["date_updated"] = datetime.now().isoformat()
            save_resources(data)
            return True
    return False

def delete_learning_resource(learning_id):
    data = load_resources()
    for i, learning in enumerate(data.get("learning_resources", [])):
        if learning["id"] == learning_id:
            data["learning_resources"].pop(i)
            save_resources(data)
            return True
    return False

def get_all_categories():
    return get_categories()


# Learning section routes
@app.route('/learning')
def learning_index():
    all_learning = get_all_learning_resources()
    categories = get_all_learning_categories()
    return render_template('learning/index.html', learning_resources=all_learning, categories=categories)

@app.route('/learning/add', methods=['GET', 'POST'])
def add_learning_resource():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        url = request.form.get('url')
        difficulty = request.form.get('difficulty', 'Medium')
        category_ids = request.form.getlist('categories')
        
        if not title or not description:
            flash('Title and description are required!')
            return redirect(url_for('add_learning_resource'))
        
        learning_id = add_learning_item(title, description, url, difficulty, category_ids)
        flash('Learning resource added successfully!')
        return redirect(url_for('learning_index'))
    
    categories = get_all_learning_categories()
    return render_template('learning/add.html', categories=categories)

@app.route('/learning/<int:learning_id>')
def view_learning(learning_id):
    learning_resource = get_learning_by_id(learning_id)
    if not learning_resource:
        flash('Learning resource not found!')
        return redirect(url_for('learning_index'))
    
    categories = get_all_learning_categories()
    
    # Get related learning resources (with similar categories)
    all_learning = get_all_learning_resources()
    related_resources = []
    
    for resource in all_learning:
        if resource['id'] != learning_id:
            # Check for shared categories
            shared_categories = set(resource['category_ids']).intersection(set(learning_resource['category_ids']))
            if shared_categories:
                related_resources.append(resource)
    
    # Limit related resources to top 3
    related_resources = related_resources[:3]
    
    # Track the view
    learning_resource['views'] = learning_resource.get('views', 0) + 1
    data = load_resources()
    save_resources(data)
    
    return render_template('learning/view.html', learning=learning_resource, categories=categories, related_resources=related_resources)

@app.route('/learning/edit/<int:learning_id>', methods=['GET', 'POST'])
def edit_learning(learning_id):
    learning_resource = get_learning_by_id(learning_id)
    if not learning_resource:
        flash('Learning resource not found!')
        return redirect(url_for('learning_index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        url = request.form.get('url')
        difficulty = request.form.get('difficulty', 'Medium')
        category_ids = request.form.getlist('categories')
        
        if not title or not description:
            flash('Title and description are required!')
            return redirect(url_for('edit_learning', learning_id=learning_id))
        
        update_learning(learning_id, title, description, url, difficulty, category_ids)
        flash('Learning resource updated successfully!')
        return redirect(url_for('view_learning', learning_id=learning_id))
    
    categories = get_all_learning_categories()
    return render_template('learning/edit.html', learning=learning_resource, categories=categories)

@app.route('/learning/delete/<int:learning_id>', methods=['POST'])
def delete_learning(learning_id):
    if delete_learning_resource(learning_id):
        flash('Learning resource deleted successfully!')
    else:
        flash('Failed to delete the learning resource.')
    return redirect(url_for('learning_index'))


@app.route("/learning/categories", methods=["GET", "POST"])
def learning_category_management():
    """Route for managing learning categories"""
    data = load_resources()
    categories = get_learning_categories()
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            # Add new category
            name = request.form.get("name")
            slug = request.form.get("slug", "").lower()
            icon = request.form.get("icon", "fas fa-book")
            
            # Validate inputs
            if not name or not slug:
                flash("Category name and slug are required")
                return redirect(url_for("learning_category_management"))
            
            # Check for duplicate slugs
            if any(c["slug"] == slug for c in categories):
                flash("A category with this slug already exists")
                return redirect(url_for("learning_category_management"))
            
            # Add new category
            new_id = max([c["id"] for c in categories], default=0) + 1
            categories.append({
                "id": new_id,
                "name": name,
                "slug": slug,
                "icon": icon
            })
            
            data["learning_categories"] = categories
            save_resources(data)
            flash("Learning category added successfully")
            
        elif action == "edit":
            # Edit existing category
            category_id = int(request.form.get("category_id"))
            name = request.form.get("name")
            slug = request.form.get("slug", "").lower()
            icon = request.form.get("icon")
            
            # Validate inputs
            if not name or not slug:
                flash("Category name and slug are required")
                return redirect(url_for("learning_category_management"))
            
            # Update category
            for category in categories:
                if category["id"] == category_id:
                    category["name"] = name
                    category["slug"] = slug
                    category["icon"] = icon
                    break
            
            data["learning_categories"] = categories
            save_resources(data)
            flash("Learning category updated successfully")
            
        elif action == "delete":
            # Delete category
            category_id = int(request.form.get("category_id"))
            
            # Check if category is in use
            learning_resources = get_all_learning_resources()
            resources_with_category = [r for r in learning_resources if category_id in r.get("category_ids", [])]
            if resources_with_category:
                flash(f"Cannot delete category because it is used by {len(resources_with_category)} learning resources")
                return redirect(url_for("learning_category_management"))
            
            # Remove category
            data["learning_categories"] = [c for c in categories if c["id"] != category_id]
            save_resources(data)
            flash("Learning category deleted successfully")
        
        return redirect(url_for("learning_category_management"))
    
    return render_template("learning/categories.html", categories=categories)


# Load learning resources
def load_learning_resources():
    if os.path.exists(app.config["JSON_FILE"]):
        with open(app.config["JSON_FILE"], "r") as f:
            data = json.load(f)
            if "learning_resources" not in data:
                data["learning_resources"] = []
            return {"resources": data["learning_resources"]}
    return {"resources": []}

@app.route("/learning/index")
def learning_resource_index():
    """Learning Resources Index - Browse learning resources by category"""
    learning = load_learning_resources()
    categories = get_learning_categories()
    return render_template(
        "learning/learning_index.html", 
        learning_resources=learning["resources"], 
        categories=categories
    )


# Notes routes
@app.route('/notes')
def view_notes():
    """Main notes landing page - redirects to the notes index dashboard"""
    return redirect(url_for('notes_index'))

@app.route('/notes/all')
def view_all_notes():
    """View for listing all notes in the traditional list format"""
    all_notes = notes.get_all_notes()
    return render_template('notes.html', notes=all_notes['notes'])

@app.route('/notes/index')
def notes_index():
    """Professional dashboard view for Notes section"""
    all_notes = notes.get_all_notes()
    return render_template('notes_index.html', notes=all_notes['notes'])

@app.route('/notes/resources')
def view_resource_notes():
    resource_notes = notes.get_notes_by_category('resources')
    return render_template('notes.html', notes=resource_notes['notes'], category='resources')

@app.route('/notes/learning')
def view_learning_notes():
    learning_notes = notes.get_notes_by_category('learning')
    return render_template('notes.html', notes=learning_notes['notes'], category='learning')

@app.route('/notes/add', methods=['GET', 'POST'])
def add_note():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']
        due_date = request.form['due_date'] if request.form['due_date'] else None
        
        notes.create_note(title, content, category, due_date)
        flash('Note added successfully!', 'success')
        return redirect(url_for('view_notes'))
    
    return render_template('add_note.html')

@app.route('/notes/<int:note_id>')
def view_note(note_id):
    note = notes.get_note_by_id(note_id)
    if note:
        return render_template('note_detail.html', note=note)
    flash('Note not found!', 'error')
    return redirect(url_for('view_notes'))

@app.route('/notes/<int:note_id>/edit', methods=['GET', 'POST'])
def edit_note(note_id):
    note = notes.get_note_by_id(note_id)
    if not note:
        flash('Note not found!', 'error')
        return redirect(url_for('view_notes'))
    
    if request.method == 'POST':
        updates = {
            'title': request.form['title'],
            'content': request.form['content'],
            'category': request.form['category'],
            'due_date': request.form['due_date'] if request.form['due_date'] else None
        }
        notes.update_note(note_id, updates)
        flash('Note updated successfully!', 'success')
        return redirect(url_for('view_note', note_id=note_id))
    
    return render_template('edit_note.html', note=note)

@app.route('/notes/<int:note_id>/toggle-complete')
def toggle_complete(note_id):
    note = notes.toggle_note_completion(note_id)
    if note:
        status = 'completed' if note['completed'] else 'marked as incomplete'
        flash(f'Note {status} successfully!', 'success')
    else:
        flash('Note not found!', 'error')
    return redirect(request.referrer or url_for('view_notes'))

@app.route('/notes/<int:note_id>/delete')
def delete_note(note_id):
    if notes.delete_note(note_id):
        flash('Note deleted successfully!', 'success')
    else:
        flash('Note not found!', 'error')
    return redirect(url_for('view_notes'))

# API endpoints for AJAX operations
@app.route('/api/notes/<int:note_id>/toggle-complete', methods=['POST'])
def api_toggle_complete(note_id):
    note = notes.toggle_note_completion(note_id)
    if note:
        return jsonify({"success": True, "note": note})
    return jsonify({"success": False, "message": "Note not found"}), 404

@app.route('/resource/<int:resource_id>/export/<format>')
def export_resource(resource_id, format):
    """Export a resource in various formats"""
    data = load_resources()
    resource = None
    
    # Find the resource
    for r in data["resources"]:
        if r["id"] == resource_id:
            resource = r
            break
    
    if not resource:
        flash("Resource not found")
        return redirect(url_for("index"))
    
    # Ensure description HTML is available
    if "description" in resource and "description_html" not in resource:
        resource["description_html"] = process_description(resource["description"])
    
    # Create export content based on format
    if format == 'pdf':
        # Generate HTML content for PDF
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{resource['name']}</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .metadata {{ color: #666; margin-bottom: 20px; }}
                .tags {{ margin: 10px 0; }}
                .tag {{ background: #f0f0f0; padding: 3px 8px; border-radius: 3px; margin-right: 5px; }}
                .content {{ line-height: 1.6; }}
            </style>
        </head>
        <body>
            <h1>{resource['name']}</h1>
            <div class="metadata">
                <p>Category: {resource['category']}</p>
                <p>Added: {resource['date_added'].split('T')[0]}</p>
                <p>Rating: {resource['rating']:.1f}/5 ({resource['ratings_count']} ratings)</p>
            </div>
            <div class="tags">
                {' '.join([f'<span class="tag">{tag}</span>' for tag in resource['tags']])}
            </div>
            <hr>
            <div class="content">
                {resource.get('description_html', '') or resource.get('description', '')}
            </div>
            <hr>
            <p>Exported from CTF Resource Management on {datetime.now().strftime('%Y-%m-%d')}</p>
        </body>
        </html>
        """
        # Generate PDF using pdfkit
        try:
            pdf = pdfkit.from_string(html_content, False, configuration=pdfkit_config)
            response = Response(pdf, mimetype="application/pdf")
            response.headers["Content-Disposition"] = f"attachment; filename={resource['name'].replace(' ', '_')}.pdf"
            return response
        except Exception as e:
            app.logger.error(f"PDF generation error: {str(e)}")
            flash("Could not generate PDF. Make sure wkhtmltopdf is installed.")
            return redirect(url_for('resource_details', resource_id=resource_id))
            
    elif format == 'md':
        # Convert HTML to Markdown if needed
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0  # No text wrapping
        
        # Build markdown content
        content = resource.get('description', '')
        if resource.get('description_html') and not content:
            content = h.handle(resource["description_html"])
            
        markdown_content = f"""# {resource['name']}

**Category:** {resource['category']}  
**Added on:** {resource['date_added'].split('T')[0]}  
**Rating:** {resource['rating']:.1f}/5 ({resource['ratings_count']} ratings)

**Tags:** {', '.join(resource['tags'])}

{content}

---
*Exported from CTF Resource Management on {datetime.now().strftime('%Y-%m-%d')}*
"""
        response = Response(markdown_content, mimetype="text/markdown")
        response.headers["Content-Disposition"] = f"attachment; filename={resource['name'].replace(' ', '_')}.md"
        return response
        
    elif format == 'html':
        # Generate standalone HTML file
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{resource['name']}</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                h1 {{ color: #333; }}
                .metadata {{ color: #666; margin-bottom: 20px; }}
                .tags {{ margin: 10px 0; }}
                .tag {{ background: #f0f0f0; padding: 3px 8px; border-radius: 3px; margin-right: 5px; display: inline-block; }}
                .content {{ margin-top: 20px; }}
                pre {{ background: #f8f8f8; padding: 10px; border-radius: 4px; overflow: auto; }}
                code {{ font-family: monospace; }}
            </style>
        </head>
        <body>
            <h1>{resource['name']}</h1>
            <div class="metadata">
                <p>Category: {resource['category']}</p>
                <p>Added: {resource['date_added'].split('T')[0]}</p>
                <p>Rating: {resource['rating']:.1f}/5 ({resource['ratings_count']} ratings)</p>
            </div>
            <div class="tags">
                {' '.join([f'<span class="tag">{tag}</span>' for tag in resource['tags']])}
            </div>
            <hr>
            <div class="content">
                {resource.get('description_html', '') or resource.get('description', '')}
            </div>
            <hr>
            <p>Exported from CTF Resource Management on {datetime.now().strftime('%Y-%m-%d')}</p>
        </body>
        </html>
        """
        response = Response(html_content, mimetype="text/html")
        response.headers["Content-Disposition"] = f"attachment; filename={resource['name'].replace(' ', '_')}.html"
        return response
    
    elif format == 'json':
        # Export as JSON
        export_data = {
            "name": resource['name'],
            "category": resource['category'],
            "tags": resource['tags'],
            "description": resource.get('description', ''),
            "url": resource.get('url', ''),
            "date_added": resource['date_added'],
            "rating": resource['rating'],
            "ratings_count": resource['ratings_count']
        }
        response = Response(json.dumps(export_data, indent=2), mimetype="application/json")
        response.headers["Content-Disposition"] = f"attachment; filename={resource['name'].replace(' ', '_')}.json"
        return response
    
    else:
        flash("Unsupported export format")
        return redirect(url_for('resource_details', resource_id=resource_id))


@app.route('/learning/<int:learning_id>/export/<format>')
def export_learning(learning_id, format):
    """Export a learning resource in various formats"""
    learning_resource = get_learning_by_id(learning_id)
    
    if not learning_resource:
        flash("Learning resource not found")
        return redirect(url_for("learning_index"))
    
    # Get categories for this learning resource
    categories = get_all_learning_categories()
    resource_categories = []
    for category in categories:
        if category["id"] in learning_resource["category_ids"]:
            resource_categories.append(category["name"])
    
    # Create export content based on format
    if format == 'pdf':
        # Generate HTML content for PDF
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{learning_resource['title']}</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .metadata {{ color: #666; margin-bottom: 20px; }}
                .categories {{ margin: 10px 0; }}
                .category {{ background: #f0f0f0; padding: 3px 8px; border-radius: 3px; margin-right: 5px; }}
                .content {{ line-height: 1.6; }}
                .difficulty {{ 
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 3px;
                    color: white;
                    background-color: {'#28a745' if learning_resource['difficulty'] == 'Easy' else '#ffc107' if learning_resource['difficulty'] == 'Medium' else '#dc3545'};
                }}
            </style>
        </head>
        <body>
            <h1>{learning_resource['title']}</h1>
            <div class="metadata">
                <p>Difficulty: <span class="difficulty">{learning_resource['difficulty']}</span></p>
                <p>Categories: {', '.join(resource_categories)}</p>
                <p>Added: {learning_resource['date_added'].split('T')[0]}</p>
                <p>Views: {learning_resource.get('views', 0)}</p>
            </div>
            <hr>
            <div class="content">
                {markdown.markdown(learning_resource['description'])}
            </div>
            <hr>
            <p>Exported from CTF Resource Management on {datetime.now().strftime('%Y-%m-%d')}</p>
        </body>
        </html>
        """
        # Generate PDF using pdfkit
        try:
            pdf = pdfkit.from_string(html_content, False, configuration=pdfkit_config)
            response = Response(pdf, mimetype="application/pdf")
            response.headers["Content-Disposition"] = f"attachment; filename={learning_resource['title'].replace(' ', '_')}.pdf"
            return response
        except Exception as e:
            app.logger.error(f"PDF generation error: {str(e)}")
            flash("Could not generate PDF. Make sure wkhtmltopdf is installed.")
            return redirect(url_for('view_learning', learning_id=learning_id))
            
    elif format == 'md':
        # Create markdown content
        markdown_content = f"""# {learning_resource['title']}

**Difficulty:** {learning_resource['difficulty']}  
**Categories:** {', '.join(resource_categories)}  
**Added on:** {learning_resource['date_added'].split('T')[0]}  
**Views:** {learning_resource.get('views', 0)}

{learning_resource['description']}

---
*Exported from CTF Resource Management on {datetime.now().strftime('%Y-%m-%d')}*
"""
        response = Response(markdown_content, mimetype="text/markdown")
        response.headers["Content-Disposition"] = f"attachment; filename={learning_resource['title'].replace(' ', '_')}.md"
        return response
        
    elif format == 'html':
        # Generate standalone HTML file
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{learning_resource['title']}</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                h1 {{ color: #333; }}
                .metadata {{ color: #666; margin-bottom: 20px; }}
                .categories {{ margin: 10px 0; }}
                .category {{ background: #f0f0f0; padding: 3px 8px; border-radius: 3px; margin-right: 5px; display: inline-block; }}
                .content {{ margin-top: 20px; }}
                pre {{ background: #f8f8f8; padding: 10px; border-radius: 4px; overflow: auto; }}
                code {{ font-family: monospace; }}
                .difficulty {{ 
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 3px;
                    color: white;
                    background-color: {'#28a745' if learning_resource['difficulty'] == 'Easy' else '#ffc107' if learning_resource['difficulty'] == 'Medium' else '#dc3545'};
                }}
            </style>
        </head>
        <body>
            <h1>{learning_resource['title']}</h1>
            <div class="metadata">
                <p>Difficulty: <span class="difficulty">{learning_resource['difficulty']}</span></p>
                <p>Categories: {', '.join([f'<span class="category">{cat}</span>' for cat in resource_categories])}</p>
                <p>Added: {learning_resource['date_added'].split('T')[0]}</p>
                <p>Views: {learning_resource.get('views', 0)}</p>
            </div>
            <hr>
            <div class="content">
                {markdown.markdown(learning_resource['description'])}
            </div>
            <hr>
            <p>Exported from CTF Resource Management on {datetime.now().strftime('%Y-%m-%d')}</p>
        </body>
        </html>
        """
        response = Response(html_content, mimetype="text/html")
        response.headers["Content-Disposition"] = f"attachment; filename={learning_resource['title'].replace(' ', '_')}.html"
        return response
    
    elif format == 'json':
        # Export as JSON
        export_data = {
            "title": learning_resource['title'],
            "difficulty": learning_resource['difficulty'],
            "categories": resource_categories,
            "description": learning_resource['description'],
            "url": learning_resource.get('url', ''),
            "date_added": learning_resource['date_added'],
            "views": learning_resource.get('views', 0)
        }
        response = Response(json.dumps(export_data, indent=2), mimetype="application/json")
        response.headers["Content-Disposition"] = f"attachment; filename={learning_resource['title'].replace(' ', '_')}.json"
        return response
    
    else:
        flash("Unsupported export format")
        return redirect(url_for('view_learning', learning_id=learning_id))


if __name__ == '__main__':
    app.run(debug=True)
