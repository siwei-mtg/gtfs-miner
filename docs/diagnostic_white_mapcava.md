                                                                                                                                 
  maplibre-gl.css sets .maplibregl-map { position: relative } (unlayered), which overrides Tailwind's .absolute { position:      
  absolute } (in @layer utilities) — because unlayered CSS always beats layered CSS in Tailwind v4. This breaks the absolute     
  inset-0 sizing pattern.                                                                                                        
                                   