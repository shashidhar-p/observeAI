import { Switch, Route, Link, useLocation } from 'react-router-dom'
import IncidentsPage from './pages/IncidentsPage'
import IncidentDetailPage from './pages/IncidentDetailPage'

function App() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-full w-16 bg-[#161b22] border-r border-gray-800 flex flex-col items-center py-4 z-50">
        <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center mb-8">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>

        <nav className="flex flex-col items-center space-y-4">
          <Link
            to="/"
            className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
              location.pathname === '/'
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:bg-gray-800 hover:text-white'
            }`}
            title="Incidents"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </Link>

          <a
            href="http://localhost:3000"
            target="_blank"
            rel="noopener noreferrer"
            className="w-10 h-10 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
            title="Grafana"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
            </svg>
          </a>
        </nav>

        <div className="mt-auto">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-800 hover:text-white transition-colors cursor-pointer" title="Settings">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-16">
        {/* Top Header */}
        <header className="h-14 bg-[#161b22] border-b border-gray-800 flex items-center justify-between px-6 sticky top-0 z-40">
          <div className="flex items-center space-x-3">
            <h1 className="text-lg font-semibold text-white">RCA Intelligence Platform</h1>
            <span className="px-2 py-0.5 bg-blue-600/20 text-blue-400 text-xs font-medium rounded">BETA</span>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-sm">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              <span className="text-gray-400">System Operational</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="p-6">
          <Switch>
            <Route exact path="/" component={IncidentsPage} />
            <Route path="/incidents/:id" component={IncidentDetailPage} />
          </Switch>
        </div>
      </main>
    </div>
  )
}

export default App
