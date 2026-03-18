import { useEffect, useRef, type FC } from 'react'
import OpenSeadragon from 'openseadragon'

interface Props {
  imageUrl: string
  onViewerReady?: (viewer: OpenSeadragon.Viewer) => void
}

const Viewer: FC<Props> = ({ imageUrl, onViewerReady }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<OpenSeadragon.Viewer | null>(null)

  // Initialise OSD une seule fois
  useEffect(() => {
    if (!containerRef.current) return

    const viewer = OpenSeadragon({
      element: containerRef.current,
      showNavigationControl: false,
      gestureSettingsMouse: { clickToZoom: false, scrollToZoom: true, dragToPan: true },
      gestureSettingsTouch: { scrollToZoom: true, dragToPan: true, pinchToZoom: true },
      animationTime: 0.3,
      minZoomLevel: 0.1,
      maxZoomLevel: 20,
    })

    viewerRef.current = viewer

    return () => {
      viewer.destroy()
      viewerRef.current = null
    }
  }, [])

  // Ouvre l'image à chaque changement d'URL
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !imageUrl) return

    viewer.open({ type: 'image', url: imageUrl })
    viewer.addOnceHandler('open', () => {
      onViewerReady?.(viewer)
    })
  }, [imageUrl]) // eslint-disable-line react-hooks/exhaustive-deps
  // onViewerReady est intentionnellement exclu : c'est un callback stable

  return (
    <div className="relative w-full h-full bg-stone-800">
      <div ref={containerRef} className="w-full h-full" />
      <div className="absolute bottom-3 right-3 flex gap-1.5">
        <button
          onClick={() => viewerRef.current?.viewport.zoomBy(1.5)}
          className="w-8 h-8 bg-stone-800/80 text-stone-200 rounded hover:bg-stone-700 text-sm font-bold"
          title="Zoom +"
        >
          +
        </button>
        <button
          onClick={() => viewerRef.current?.viewport.zoomBy(0.67)}
          className="w-8 h-8 bg-stone-800/80 text-stone-200 rounded hover:bg-stone-700 text-sm font-bold"
          title="Zoom −"
        >
          −
        </button>
        <button
          onClick={() => viewerRef.current?.viewport.goHome()}
          className="w-8 h-8 bg-stone-800/80 text-stone-200 rounded hover:bg-stone-700 text-xs"
          title="Réinitialiser"
        >
          ⊙
        </button>
        <button
          onClick={() => viewerRef.current?.setFullScreen(true)}
          className="w-8 h-8 bg-stone-800/80 text-stone-200 rounded hover:bg-stone-700 text-xs"
          title="Plein écran"
        >
          ⛶
        </button>
      </div>
    </div>
  )
}

export default Viewer
