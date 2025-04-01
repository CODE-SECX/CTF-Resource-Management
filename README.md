# CTF Resource Management System

A centralized repository for cybersecurity tools, scripts, cheatsheets, and references designed specifically for CTF (Capture The Flag) participants.

## Features

- **Centralized Repository**: Store and organize cybersecurity tools, scripts, and references
- **Multi-tag Categorization**: Tag resources with multiple relevant labels for easy filtering
- **Category Classification**: Main categories include Web Exploitation, Cryptography, Reverse Engineering, etc.
- **Advanced Filtering**: Search by keywords, tags, and date
- **Interactive Table View**: Sortable columns with expandable detailed views
- **User Contributions**: Community-driven resource addition with proper tagging
- **Dark Mode**: Eye-friendly interface for extended usage
- **User Accounts**: Track contributions and favorites
- **Rating System**: Community feedback on resource usefulness
- **Markdown Support**: Rich text formatting for resource descriptions
- **Export Functionality**: Download resources for offline use

## Technology Stack

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, JavaScript
- **Storage**: JSON-based file storage
- **Authentication**: Flask-Login
- **UI Framework**: Bootstrap 5
- **Icons**: Font Awesome
- **Markdown Processing**: Python Markdown

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd ctf-resource-management
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

5. Open your browser and navigate to `http://localhost:5000`

## Usage

### For Users

1. **Browse Resources**:
   - Use the search bar to find specific resources
   - Filter by category using the sidebar
   - Click on resource names to view details
   - Rate resources using the star system

2. **Account Features**:
   - Register for an account to access additional features
   - Add resources to your favorites
   - Contribute new resources to the community
   - Rate and review existing resources

3. **Dark Mode**:
   - Toggle dark mode using the moon icon in the navigation bar
   - Your preference will be saved for future visits

### For Contributors

1. **Adding Resources**:
   - Log in to your account
   - Click the "Add Resource" button
   - Fill in the resource details:
     - Name
     - Category
     - Tags (comma-separated)
     - Description (Markdown supported)
     - URL

2. **Resource Guidelines**:
   - Use clear, descriptive names
   - Add relevant tags for better discoverability
   - Provide detailed descriptions
   - Include proper documentation links
   - Follow the existing categorization system

## Data Structure

Resources are stored in `resources.json` with the following structure:

```json
{
  "resources": [
    {
      "id": 1,
      "name": "Resource Name",
      "category": "category_name",
      "tags": ["tag1", "tag2"],
      "description": "Markdown formatted description",
      "url": "https://resource-url.com",
      "date_added": "2023-01-01T00:00:00",
      "added_by": "username",
      "rating": 4.5,
      "ratings_count": 10
    }
  ],
  "users": [
    {
      "id": 1,
      "username": "username",
      "password_hash": "hashed_password"
    }
  ],
  "favorites": {
    "user_id": [resource_id1, resource_id2]
  }
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Bootstrap for the UI framework
- Font Awesome for icons
- The CTF community for inspiration and feedback 