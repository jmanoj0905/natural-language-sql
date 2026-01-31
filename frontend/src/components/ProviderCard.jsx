import {
  Database,
  Container,
  Cloud,
  CloudCog,
  Waves,
  Zap,
  Train,
  Palette,
  CircleDot,
  Globe,
  Settings,
  Server,
  Check
} from 'lucide-react'

// Provider card component for visual provider selection

const ICON_COMPONENTS = {
  database: Database,
  docker: Container,
  aws: Cloud,
  gcp: CloudCog,
  azure: Cloud,
  digitalocean: Waves,
  supabase: Zap,
  railway: Train,
  render: Palette,
  heroku: CircleDot,
  neon: Zap,
  planetscale: Globe,
  settings: Settings
}

const BADGE_COLORS = {
  Local: 'bg-green-100 text-green-800',
  Container: 'bg-blue-100 text-blue-800',
  Cloud: 'bg-purple-100 text-purple-800',
  Platform: 'bg-orange-100 text-orange-800',
  Serverless: 'bg-pink-100 text-pink-800',
  Popular: 'bg-yellow-100 text-yellow-800',
  Custom: 'bg-gray-100 text-gray-800'
}

export default function ProviderCard({ provider, selected, onClick }) {
  const IconComponent = ICON_COMPONENTS[provider.icon] || Server
  const badgeColor = BADGE_COLORS[provider.badge] || 'bg-gray-100 text-gray-800'

  return (
    <div
      onClick={onClick}
      className={`
        relative p-5 border-2 rounded-lg cursor-pointer transition-all
        ${selected
          ? 'border-blue-600 bg-blue-600 text-white shadow-lg scale-105'
          : 'border-gray-200 bg-white hover:border-blue-400 hover:shadow-md'
        }
      `}
    >
      {/* Icon */}
      <div className="mb-3">
        <IconComponent
          size={40}
          className={selected ? 'text-white' : 'text-blue-600'}
          strokeWidth={1.5}
        />
      </div>

      {/* Name and DB Type */}
      <div className="mb-2">
        <h3 className={`font-semibold text-lg ${selected ? 'text-white' : 'text-gray-900'}`}>
          {provider.name}
        </h3>
        <p className={`text-xs mt-1 uppercase font-medium ${selected ? 'text-blue-100' : 'text-gray-500'}`}>
          {provider.dbType}
        </p>
      </div>

      {/* Description */}
      <p className={`text-sm mt-2 min-h-[40px] ${selected ? 'text-blue-50' : 'text-gray-600'}`}>
        {provider.description}
      </p>

      {/* Badge */}
      {provider.badge && (
        <span className={`
          inline-block mt-3 px-2 py-1 text-xs rounded font-medium
          ${selected ? 'bg-white bg-opacity-20 text-white' : badgeColor}
        `}>
          {provider.badge}
        </span>
      )}

      {/* Checkmark if selected */}
      {selected && (
        <div className="absolute top-3 right-3 flex items-center justify-center w-6 h-6 bg-white rounded-full">
          <Check size={16} className="text-blue-600" strokeWidth={3} />
        </div>
      )}
    </div>
  )
}
