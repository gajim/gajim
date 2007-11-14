#import <Cocoa/Cocoa.h>


@interface NSApplication (Gajim)

- (void) initGajim;
- (void) initGUI;
- (BOOL) initNetNotify;
- (void) orderFrontStandardAboutPanel: (id)sender;
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender;
- (BOOL) application:(NSApplication *)theApplication 
             openFile:(NSString *)filename;
- (void) application:(NSApplication *)sender openFiles:(NSArray *)filenames;
- (BOOL) applicationOpenUntitledFile:(NSApplication *)theApplication;
- (BOOL) applicationShouldOpenUntitledFile:(NSApplication *)sender;

+ (void) netNotifyCB: (NSNotification*)notif;

@end
