export default function ConnectionStatusIndicator({ isConnected }) {
  return (
    <div
      className={`h-2.5 w-2.5 rounded-full ${
        isConnected ? 'bg-green-500' : 'bg-gray-400'
      }`}
      title={isConnected ? 'Connected' : 'Not connected'}
    />
  )
}
