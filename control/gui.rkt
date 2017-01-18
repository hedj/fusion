#lang racket/gui

; we rely on the third-party irc library
(require irc)
(require racket/gui/base)
(require racket/async-channel)

; join the IRC Channel
(define-values (connection ready)
(irc-connect "localhost" 6667 "guibot" "gui" "GUI bot"))
(irc-join-channel connection "#foo")

(define (debug-print x) (println x) (flush-output))

(sync ready)

(define (handle-message x) (
(let ([pref (irc-message-prefix x)] [par (irc-message-parameters x)] [cmd (irc-message-command x)]) 
  (lambda () (debug-print (list pref par cmd) ))
))
)

(thread ( lambda () (let ([c (irc-connection-incoming connection)]) (for ([i (in-naturals)]) (handle-message (async-channel-get c)  )))))

; define some helpers

(define (lines s) (string-split s "\n" #:trim? #t))

(define (starts-with s c)
  (equal? (first (string->list s)) c))

(define (valid-special-line s) 
  (or (starts-with s #\#) (starts-with s #\!) (starts-with s #\@))
)

(define (valid-line s)
  (or (valid-special-line s) (valid-sequence-line s))
)

(define (valid-sequence-line s) 
  (equal? (length (string-split s #:trim? #t)) 8)
)

(define (valid-sequence s)
  (for/list ([l (lines s)]) (valid-line l))
)

(define (validate-sequence s) 
  (if (equal? s "")
      (void) 
      (if (first (and (valid-sequence s))) (message-box "Info" "Valid sequence") (message-box "Info" "Invalid sequence"))
  )
)

(define blackColor (make-color 0 0 0))

(define (getlabel r)
  (send r get-item-label (send r get-selection)) )

(define (bankbot-command content-string) 
  (irc-send-message connection "#foo" (string-append "bank: " content-string)))

(define (stepper-forward d) 
  (irc-send-message connection "#foo" (string-append "stepper: F" (~a d))))

(define (stepper-reverse d) 
  (irc-send-message connection "#foo" (string-append "stepper: R" (~a d))))
                    

(define (set-widths widths)
  (for ([i (length widths)]) ( bankbot-command (string-append "set pulse_width " (~a (+ i 1)) " " (~a (list-ref widths i)) )  )))

(define (set-delays delays)
  (for ([i (length delays)]) ( bankbot-command (string-append "set pulse_delay " (~a (+ i 1)) " " (~a (list-ref delays i)) )  )))

(define (new-vert-group p lbl) 
  ( new vertical-panel% (parent (new group-box-panel% (parent p) (label lbl)) )))

(define (new-horiz-group p lbl) 
  ( new horizontal-panel% (parent (new group-box-panel% (parent p) (label lbl)) )))


; Construct the GUI
(define hiddenframe (new frame% [label ""]))
(define frame (new frame% [label "Automation GUI"]))
(define menu-bar (new menu-bar%
                      (parent frame)))
(define filemenu (new menu%
     (label "&File")
     (parent menu-bar)))

(new menu-item% (label "Load Sequence") (parent filemenu) (callback (lambda (m e) (list
                                                                      (send sequence-editor erase)  
                                                                      (send sequence-editor insert (file->string (get-file))  0 )
                                                                      ))))
(new menu-item% (label "Save Sequence as ...") (parent filemenu) (callback (lambda (m e) (send sequence-editor save-file (put-file) 'text) )))
(new menu-item% (label "Quit") (parent filemenu) (callback (lambda (m e) (exit) )))

(define tabs (make-hash))

(define tab-panel (new tab-panel%
                       (parent frame)
                       (choices (list "Control"
                                      "Acquisition"
                                      "Sequencing"))
  [callback (lambda (t e) (
    case (getlabel t) 
     [("Control") (send t change-children (lambda (children) (list (hash-ref tabs "Control"))))]
     [("Acquisition") (send t change-children (lambda (children) (list (hash-ref tabs "Acquisition"))))]
     [("Sequencing") (send t change-children (lambda (children) (list (hash-ref tabs "Sequencing"))))]
  )) ]
))

(define control-elements (new vertical-panel% (parent tab-panel)))
(hash-set! tabs "Control" control-elements)

; Define the Sequencing controls
(define sequencing-elements (new vertical-panel% (parent tab-panel)))
(hash-set! tabs "Sequencing" sequencing-elements)

(define sequence-controls (new-horiz-group sequencing-elements "Sequence control" ))

(new button% (parent sequence-controls) (label "Validate") [ callback (lambda (c e) ( validate-sequence  (send sequence-editor get-text) ) )] )
(new button% (parent sequence-controls) (label "Start") )
(new button% (parent sequence-controls) (label "Stop") )
(new button% (parent sequence-controls) (label "Reset") )
(new button% (parent sequence-controls) (label "Clear") [callback (lambda (c e) ( send sequence-editor erase   ))] )

(define c (new editor-canvas% [parent sequencing-elements]))
(define sequence-editor (new text%))
(send c set-editor sequence-editor)


(define voltage-display
(new canvas% [parent control-elements]
             [min-width 400]
             [min-height 300]
             [paint-callback
              (lambda (canvas dc)
                (send dc set-scale 3 3)
                (send dc set-text-foreground "blue")
                (send dc draw-text "Don't Panic!" 0 0))]))

(send voltage-display set-canvas-background blackColor)


(define charge-panel (new group-box-panel% (parent control-elements) (label "Power Supplies") ))
(define stepper-panel (new group-box-panel% (parent control-elements) (label "Stepper Control") ))


(define holder (new horizontal-panel% (parent stepper-panel))) 

(define stepper-slider (new slider%
                    (label "Step Size (mm)")
                    (parent holder)
                    (min-value 0)
                    (max-value 20)
                    (init-value 0)))

(new button% [parent holder] [label "Forward"]
  [ callback (lambda (button event) (stepper-forward (send stepper-slider get-value) )) ]
)

(new button% [parent holder] [label "Reverse"]
  [ callback (lambda (button event) (stepper-reverse (send stepper-slider get-value) )) ]
)


(define charge-horiz (new horizontal-panel% (parent charge-panel)))

(new radio-box% [parent charge-horiz] [label "Charge Enable"] [choices (list "off" "on")]
  [ callback (lambda (r e)
               (bankbot-command (string-append "set charge_enable " (getlabel r))  ))])

(new radio-box% [parent charge-horiz] [label "Charge Power"] [choices (list "off" "on")]
  [ callback (lambda (r e) (bankbot-command (string-append "set charge_power " (getlabel r))  ))  ])

(new radio-box% [parent charge-horiz] [label "HV Enable"] [choices (list "off" "on")]
  [ callback (lambda (r e) (bankbot-command (string-append "set hv_enable " (getlabel r))  ))  ])

(define charge-horiz-two (new horizontal-panel% (parent charge-panel)))
(define cap-voltage-controls (new-vert-group charge-horiz-two "Cap Bank"))
(define hv-voltage-controls (new-vert-group charge-horiz-two "HV"))


(define charge-slider (new slider%
                    (label "Target Voltage")
                    (parent cap-voltage-controls)
                    (min-value 0)
                    (max-value 900)
                    (init-value 0)))

(new button% [parent cap-voltage-controls] [label "Charge Capacitor Bank!"]
  [ callback (lambda (button event) ( bankbot-command (string-append "charge " (~a (send charge-slider get-value) ) ) )) ]     
)

(define hv-slider (new slider%
                    (label "Target Voltage")
                    (parent hv-voltage-controls)
                    (min-value 0)
                    (max-value 50000)
                    (init-value 0)))

(new button% [parent hv-voltage-controls] [label "Set Spellman Voltage!"]

  [ callback (lambda (button event) (bankbot-command (string-append "set " "hv_voltage " (~a  (send hv-slider get-value )))))])

(define horiz-holder (new horizontal-panel% (parent charge-panel)))

(define width-slider-panel (new-vert-group horiz-holder "Pulse Width"))
(define delay-slider-panel (new-vert-group horiz-holder "Pulse Delay"))

(define width-sliders
(for/list ([bank '("Bank 1 " "Bank 2 " "Bank 3 " "Bank 4 " "      HV ") ])
  ( new slider% (parent width-slider-panel) (label bank  )(min-value 0) (max-value 128) (init-value 100) ) )
)

(define delay-sliders
(for/list ([bank '("Bank 1 " "Bank 2 " "Bank 3 " "Bank 4 " "      HV ") ])
  ( new slider% (parent delay-slider-panel) (label bank  )(min-value 0) (max-value 128) (init-value 0) ) )
)

(define (get-widths x) (for/list ([w width-sliders]) ( send w get-value ) ))
(define (get-delays x) (for/list ([w delay-sliders]) ( send w get-value ) ))

(new button% [parent charge-panel] [label "Pulse"]
     [ callback (lambda (button event) (set-widths (get-widths 0)) (set-delays (get-delays 0)) (bankbot-command "pulse"))
     ])

(new message% [parent frame] [ label "Status: OK" ])


; Show the GUI
(send frame show #t)
(send tab-panel change-children (lambda (children) (list (hash-ref tabs "Control"))))
