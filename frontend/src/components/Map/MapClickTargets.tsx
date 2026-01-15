/**
 * Component to render map-click targets as pins and labels on the Cesium globe
 */

import React from 'react'
import { Entity, LabelGraphics, PointGraphics } from 'resium'
import { 
  Cartesian3, 
  Color, 
  VerticalOrigin, 
  HorizontalOrigin,
  HeightReference,
  NearFarScalar,
  DistanceDisplayCondition
} from 'cesium'
import { TargetData } from '../../types'

interface MapClickTargetsProps {
  targets: TargetData[]
  visible?: boolean
}

export const MapClickTargets: React.FC<MapClickTargetsProps> = ({ targets, visible = true }) => {
  return (
    <>
      {targets.map((target, index) => {
        const position = Cartesian3.fromDegrees(
          target.longitude,
          target.latitude,
          0
        )

        return (
          <Entity
            key={`map-click-target-${index}`}
            id={`map-click-target-${index}`}
            name={target.name}
            position={position}
            show={visible}
            description={target.description || undefined}
          >
            {/* Pin point */}
            <PointGraphics
              pixelSize={10}
              color={Color.RED}
              outlineColor={Color.WHITE}
              outlineWidth={2}
              heightReference={HeightReference.CLAMP_TO_GROUND}
            />
            
            {/* Label */}
            <LabelGraphics
              text={target.name}
              font="14px sans-serif"
              fillColor={Color.WHITE}
              outlineColor={Color.BLACK}
              outlineWidth={2}
              style={0} // LabelStyle.FILL_AND_OUTLINE
              verticalOrigin={VerticalOrigin.BOTTOM}
              horizontalOrigin={HorizontalOrigin.LEFT}
              pixelOffset={new Cartesian3(10, 0, 0)}
              heightReference={HeightReference.CLAMP_TO_GROUND}
              distanceDisplayCondition={new DistanceDisplayCondition(0, 10000000)}
              scaleByDistance={new NearFarScalar(1000, 1.0, 5000000, 0.5)}
            />
          </Entity>
        )
      })}
    </>
  )
}
