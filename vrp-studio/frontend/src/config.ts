type VrpStudioRuntimeConfig = {
  API_BASE_URL?: string
  WS_BASE_URL?: string
  BACKEND_PROTOCOL?: string
  BACKEND_HOST?: string
  BACKEND_PORT?: string | number
}

declare global {
  interface Window {
    VRP_STUDIO_CONFIG?: VrpStudioRuntimeConfig
  }
}

const runtimeConfig = window.VRP_STUDIO_CONFIG ?? {}

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, '')

const getConfiguredHttpOrigin = (): string => {
  if (runtimeConfig.API_BASE_URL) {
    return trimTrailingSlash(runtimeConfig.API_BASE_URL)
  }

  const protocol = (runtimeConfig.BACKEND_PROTOCOL || window.location.protocol).replace(/:$/, '')
  const host = runtimeConfig.BACKEND_HOST || window.location.hostname
  const port = runtimeConfig.BACKEND_PORT ?? window.location.port
  const portPart = port ? `:${port}` : ''

  return `${protocol}://${host}${portPart}`
}

const getConfiguredWsOrigin = (): string => {
  if (runtimeConfig.WS_BASE_URL) {
    return trimTrailingSlash(runtimeConfig.WS_BASE_URL)
  }

  const httpOrigin = getConfiguredHttpOrigin()
  if (httpOrigin.startsWith('https://')) {
    return `wss://${httpOrigin.slice('https://'.length)}`
  }
  if (httpOrigin.startsWith('http://')) {
    return `ws://${httpOrigin.slice('http://'.length)}`
  }

  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${wsProtocol}://${httpOrigin}`
}

export const getApiUrl = (path: string): string => `${getConfiguredHttpOrigin()}${path}`

export const getWsUrl = (path: string): string => `${getConfiguredWsOrigin()}${path}`
