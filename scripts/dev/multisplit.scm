; multisplit: splits up a mavica multi (sprites in one layer) into layers
; so you make make from png/jpg sprite a gif animation
; put me in ~/.gimp-ver/scripts and find me script-fu>animators>MultiSplit

(define (script-fu-multisplit multimg
			      drawable
			      horizontal
			      vertical
			      delay)
 (let* (
        (width 0)
        (height 0)
	(img 0)
	(layerNum 0)
	(hpos 0)
	(vpos 0)
	(layer 0)
	(floatingLayer 0)
       )

  (set! width (/ (car (gimp-image-width multimg)) horizontal))
  (set! height (/ (car (gimp-image-height multimg)) vertical))
  (set! img (car (gimp-image-new width height RGB)))

  (set! vpos 0)
  (while (< vpos vertical)
    (set! hpos 0)
    (while (< hpos horizontal) 
      (set! layerNum (+ layerNum 1))
      (set! layer (car (gimp-layer-new img width height RGB
                   (string-append "Frame" delay "(replace)")
		   100 NORMAL)))

      (gimp-layer-add-alpha layer)
      (gimp-drawable-fill layer TRANSPARENT-FILL)
      (gimp-image-add-layer img layer -1)

      (gimp-rect-select multimg
        (* hpos width) (* vpos height)
	width height
	REPLACE FALSE 0)

      (gimp-edit-copy drawable)

      (gimp-selection-all img)

      (set! floatingLayer (car (gimp-edit-paste layer 0)))
      (gimp-floating-sel-anchor floatingLayer)

      (gimp-selection-none img)
      (gimp-selection-none multimg)
      
      (set! hpos (+ hpos 1))
    )
    (set! vpos (+ vpos 1))
  )

  (gimp-display-new img)
 )
)

(script-fu-register "script-fu-multisplit" 
		    "<Image>/Script-Fu/Animators/MultiSplit"
		    "Split an image into layers"
		    "Rick Miller (Rick.Miller@Linux.org)"
		    "Rick Miller"
		    "05/19/2000"
		    "RGB RGBA GRAY GRAYA"
		    SF-IMAGE "Image" 0
		    SF-DRAWABLE "Drawable" 0
		    SF-VALUE "Horizontal Slices" "3"
		    SF-VALUE "Vertical Slices" "3"
		    SF-VALUE "Default Delay" "\"250ms\"")

