import { useState, useEffect, useRef } from 'react'
import { MapContainer, ImageOverlay, GeoJSON, useMapEvent } from 'react-leaflet'
import { LatLngTuple, CRS } from 'leaflet'

import Control from './components/Control'
import SettingModal from './components/Setting'
import { retrieveObject, listObjects, generateCompositeName } from './utils/s3client'
import { CompositeListType, CompositeType, ImageType } from './utils/types'
import lands from './natural-earth.json'
import firs from './firs.json'

import 'leaflet/dist/leaflet.css'


const MousePosition: React.FC = () => {
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(null)

  useMapEvent('mousemove', (e) => {
      setPosition({ lat: e.latlng.lat, lng: e.latlng.lng })
  })

  useMapEvent('mouseout', () => {
      setPosition(null)
  })

  return (
      <div>
          {position && (
              <div className='text-stroke'>
                  {position.lat.toFixed(4)}, {position.lng.toFixed(4)} 
              </div>
          )}
      </div>
  )
}

function App() {
  const position: LatLngTuple = [21, 115]
  const maxBounds: [LatLngTuple, LatLngTuple] = [
      [0, 98], // south west
      [30, 137] // north east
    ]

  const [image, setImage] = useState<ImageType>()
  const [compositeName, setCompositeName] = useState<CompositeType>('ir_clouds')
  const [composites, setComposites] = useState<CompositeListType>({ir_clouds: [], true_color: []})
  const [playing, setPlaying] = useState<boolean>(false)
  const [, setCurrentIndex] = useState<number>(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [settingVisible, setSettingVisible] = useState(false)

  const handlePlayClick = () => {
    setPlaying(prev => !prev)
    console.log('play', playing)
  }

  const handleSettingClick = () => {
    setSettingVisible(prev => !prev)
  }

  const handleCompositeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setCompositeName(event.target.value as CompositeType)
  }

  const fetchImage = async (object: ImageType) => {
    const url = await retrieveObject(object.key)
    const currentImage: ImageType = {
      datetime: object.datetime,
      key: object.key,
      url: url
    }
    setImage(currentImage)
  }

  useEffect(() => {
    const fetchComposites = async () => {
      const startAfter = generateCompositeName(24)
      const objects = await listObjects(startAfter)
      setComposites(objects)
      console.log('update composite objects after', startAfter)
    }

    fetchComposites()
    const intervalId = setInterval(fetchComposites, 60000)

    return () => clearInterval(intervalId)
  }, [])

  useEffect(() => {
    let images = composites[compositeName]

    if (playing) {
      intervalRef.current = setInterval(() => {
        setCurrentIndex(prevIndex => {
          const nextIndex = (prevIndex + 1) % images.length
          const currentImage = images[nextIndex]
          fetchImage(currentImage)
          return nextIndex
        })
      }, 200)

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
        }
      }
    }
    else {
      if (images.length > 0) {
        const latestObject = images[images.length - 1]
        fetchImage(latestObject)
        setCurrentIndex(0)
      }
    }
  }, [playing, composites, compositeName])

  return (
        <MapContainer 
          center={position}
          maxBoundsViscosity={1.0}
          zoom={6}
          minZoom={5}
          maxZoom={10}
          maxBounds={maxBounds}
          crs={CRS.Simple}
        >
          {/* <TileLayer url='https://{s}.basemaps.cartocdn.com/rastertiles/dark_nolabels/{z}/{x}/{y}.png' /> */}
          {image &&
            <ImageOverlay bounds={maxBounds} url={image.url as string} />
          }
          <GeoJSON 
            data={lands as GeoJSON.GeoJsonObject}
            style={{
              color: '#828282',
              weight: 2,
              opacity: 1,
              fillOpacity: 0
            }}
          />
          <GeoJSON 
            data={firs as GeoJSON.GeoJsonObject}
            style={{
              color: '#c8c8c8',
              weight: 2,
              opacity: 1,
              fillOpacity: 0
            }}
          />
          <Control position='topright'>
            <div className='leaflet-control-layers leaflet-control-layers-expanded'>
              <label>
                  <input
                      type='radio'
                      name='ir_clouds'
                      className='leaflet-control-layers-selector'
                      value='ir_clouds'
                      checked={compositeName === 'ir_clouds'}
                      onChange={handleCompositeChange}
                  />
                  Himawari IR Clouds
              </label>
              <label>
                  <input
                      type='radio'
                      name='true_color'
                      className='leaflet-control-layers-selector'
                      value='true_color'
                      checked={compositeName === 'true_color'}
                      onChange={handleCompositeChange}
                  />
                  Himawari True Color
              </label>
            </div>
          </Control>
          <Control position='topleft'>
            <button 
              className='leaflet-bar leaflet-icon-button'
              onClick={handlePlayClick}
            >{playing ? 'Stop' : 'Play'}</button>
            <br/>
            <button 
              className='leaflet-bar leaflet-icon-button'
              onClick={handleSettingClick}>
              Pref
            </button>
          </Control>
          <Control position='bottomleft'>
            <MousePosition/>
          </Control>
          <Control position='bottomright'>
            {image && (
              <div className='text-stroke'>
                  {image.datetime.format('YYYY-MM-DD HH:mm')}
              </div>
            )}
          </Control>
          <SettingModal visible={settingVisible} handleClose={handleSettingClick} />
        </MapContainer>
  )
}

export default App
