from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import json
import os
from datetime import datetime
import markdown
from collections import Counter
import difflib

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['JSON_FILE'] = 'resources.json'

# Load resources from JSON file
def load_resources():
    if os.path.exists(app.config['JSON_FILE']):
        with open(app.config['JSON_FILE'], 'r') as f:
            return json.load(f)
    return {'resources': []}

# Save resources to JSON file
def save_resources(data):
    with open(app.config['JSON_FILE'], 'w') as f:
        json.dump(data, f, indent=4)

def get_similar_resources(resource, all_resources, limit=3):
    """Find similar resources based on tags and category"""
    similar = []
    for r in all_resources:
        if r['id'] != resource['id']:
            # Calculate similarity score
            tag_similarity = len(set(resource['tags']) & set(r['tags'])) / len(set(resource['tags']) | set(r['tags']))
            category_match = 1 if r['category'] == resource['category'] else 0
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
    for resource in data['resources']:
        all_tags.extend(resource['tags'])
    return [tag for tag, count in Counter(all_tags).most_common(limit)]

@app.route('/')
def index():
    data = load_resources()
    popular_tags = get_popular_tags()
    return render_template('index.html', 
                         resources=data['resources'],
                         popular_tags=popular_tags)

@app.route('/resource/<int:resource_id>')
def resource_details(resource_id):
    data = load_resources()
    for resource in data['resources']:
        if resource['id'] == resource_id:
            # Convert markdown description to HTML if it exists
            if 'description' in resource:
                resource['description_html'] = markdown.markdown(resource['description'])
            
            # Get similar resources
            similar_resources = get_similar_resources(resource, data['resources'])
            
            # Track view count
            if 'views' not in resource:
                resource['views'] = 0
            resource['views'] += 1
            save_resources(data)
            
            return render_template('resource_details.html', 
                                 resource=resource,
                                 similar_resources=similar_resources)
    flash('Resource not found')
    return redirect(url_for('index'))

@app.route('/api/resources')
def get_resources():
    data = load_resources()
    return jsonify(data['resources'])

@app.route('/api/resources', methods=['POST'])
def add_resource():
    data = load_resources()
    new_resource = request.json
    new_resource['id'] = len(data['resources']) + 1
    new_resource['date_added'] = datetime.now().isoformat()
    new_resource['added_by'] = 'Anonymous'
    new_resource['rating'] = 0
    new_resource['ratings_count'] = 0
    new_resource['views'] = 0
    
    data['resources'].append(new_resource)
    save_resources(data)
    return jsonify(new_resource), 201

@app.route('/api/resources/<int:resource_id>/rate', methods=['POST'])
def rate_resource(resource_id):
    data = load_resources()
    rating = request.json.get('rating')
    
    for resource in data['resources']:
        if resource['id'] == resource_id:
            resource['rating'] = ((resource['rating'] * resource['ratings_count']) + rating) / (resource['ratings_count'] + 1)
            resource['ratings_count'] += 1
            break
    
    save_resources(data)
    return jsonify({'message': 'Rating updated successfully'})

@app.route('/api/tags/suggestions')
def get_tag_suggestions():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
    
    data = load_resources()
    all_tags = set()
    for resource in data['resources']:
        all_tags.update(resource['tags'])
    
    # Find matching tags using fuzzy matching
    matches = difflib.get_close_matches(query, all_tags, n=5, cutoff=0.3)
    return jsonify(matches)

@app.route('/api/analytics')
def get_analytics():
    data = load_resources()
    
    # Category distribution
    categories = Counter(r['category'] for r in data['resources'])
    
    # Popular tags
    all_tags = []
    for resource in data['resources']:
        all_tags.extend(resource['tags'])
    popular_tags = Counter(all_tags).most_common(10)
    
    # Most viewed resources
    most_viewed = sorted(data['resources'], 
                        key=lambda x: x.get('views', 0), 
                        reverse=True)[:5]
    
    # Most rated resources
    most_rated = sorted(data['resources'], 
                       key=lambda x: x.get('ratings_count', 0), 
                       reverse=True)[:5]
    
    return jsonify({
        'categories': dict(categories),
        'popular_tags': dict(popular_tags),
        'most_viewed': [{'id': r['id'], 'name': r['name'], 'views': r.get('views', 0)} for r in most_viewed],
        'most_rated': [{'id': r['id'], 'name': r['name'], 'rating': r['rating'], 'ratings_count': r.get('ratings_count', 0)} for r in most_rated]
    })

if __name__ == '__main__':
    app.run(debug=True)