# Natural Language SQL Engine - Frontend

Modern React frontend with Tailwind CSS for the Natural Language SQL Query Engine.

## Features

- **Natural Language Query Interface** - Ask questions in plain English
- **Results Display** - Beautiful table view of query results
- **Schema Viewer** - Browse database tables and columns
- **Query History** - View past queries and results
- **Database Status** - Real-time connection health monitoring
- **Safety Indicators** - Read-only mode warnings
- **Fast & Responsive** - Built with React + Vite
- **Beautiful UI** - Tailwind CSS styling

## Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

The frontend will start at http://localhost:3000

### 3. Make Sure Backend is Running

The backend must be running at http://localhost:8000

```bash
# In the root directory
uvicorn app.main:app --reload
```

## Usage

### Ask Questions

1. Go to the **Query** tab
2. Type your question in plain English
3. Click "Generate SQL & Execute"
4. View the generated SQL, explanation, and results

**Example Questions:**
- "Show me all users"
- "Find products under $50"
- "What are the top 5 most expensive products?"
- "Show orders from the last week"

### View Schema

1. Go to the **Schema** tab
2. Browse all tables and columns
3. Click on a table to expand and see column details

### View History

1. Go to the **History** tab
2. See all past queries
3. Review SQL and results

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── DatabaseStatus.jsx    # DB connection indicator
│   │   ├── QueryInterface.jsx    # Main query input
│   │   ├── ResultsDisplay.jsx    # Results table
│   │   ├── SchemaViewer.jsx      # Schema browser
│   │   └── QueryHistory.jsx      # Query history
│   ├── App.jsx                    # Main app component
│   ├── main.jsx                   # React entry point
│   └── index.css                  # Tailwind styles
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

## API Integration

The frontend connects to the FastAPI backend at `/api/v1`:

- `POST /api/v1/query/natural` - Submit natural language queries
- `GET /api/v1/health/database` - Check database status
- `GET /api/v1/schema` - Get database schema (to be implemented)

## Build for Production

```bash
npm run build
```

The production build will be in the `dist/` directory.

## Tech Stack

- **React 18** - UI library
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Axios** - HTTP client

## Customization

### Colors

Edit `tailwind.config.js` to customize the color scheme.

### API Base URL

Edit `vite.config.js` proxy settings to change the backend URL.

## Future Enhancements

- [ ] Implement real schema viewer with backend integration
- [ ] Add query export (CSV, JSON)
- [ ] Add query bookmarks/favorites
- [ ] Add dark mode
- [ ] Add query suggestions
- [ ] Add result pagination
- [ ] Add charts and visualizations
- [ ] Add multi-database switcher

## Troubleshooting

**Frontend not loading?**
- Make sure you ran `npm install`
- Check that port 3000 is available
- Try clearing browser cache

**API errors?**
- Verify backend is running at http://localhost:8000
- Check browser console for errors
- Verify CORS is enabled in backend

**Style issues?**
- Make sure Tailwind CSS is properly configured
- Check `index.css` is imported in `main.jsx`
- Try rebuilding with `npm run dev`

---

Built using React, Tailwind CSS, and FastAPI
