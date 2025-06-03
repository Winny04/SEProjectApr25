# Added the ( add, edit, delete function with auto save), need to import file first before anything. then just edit and it will auto save no need to export again
What you need to add for your described workflow:
User Role Management (Product Owner vs Admin)
Implement user role selection.

Product Owners can only submit new samples (which are stored as pending).
Admin can view pending samples and approve/reject them.

Pending vs Approved Data Separation
Maintain two datasets in the Excel file or separate files/tabs:
Pending Requests (entered by Product Owners, awaiting Admin approval)
Approved Samples (final data used for barcode, tracking, reporting)

Approval Workflow
Product Owners add samples → saved to Pending sheet/section.
Admin views Pending entries → approves → entry moves from Pending to Approved sheet.
Only Approved entries get saved in the main data view and barcode generated.

Excel Data Structure
Use multiple sheets in the Excel workbook (e.g., "Pending", "Approved") or multiple Excel files.
Your code will load both Pending and Approved data on startup or on-demand.

GUI Adjustments
role selection UI.
Product Owner UI: can add requests, view status. No editing/deleting approved samples.
Admin UI: can view all approved + pending samples, approve/reject pending ones.
Barcode generation only for approved samples.

Data Saving & Consistency
Save changes to Excel after approval moves data.
Keep Excel file as your “database” for simplicity, but clearly separate data states.

By boon, (later i go back home continue.....)




# Added the ( add, edit, delete function with auto save) 
# need to import file first before anything. then just edit and it will auto save no need to export again

# SEProjectApr25

# yay :D

# lol😎

# byeee :)

# sleepy🥱😪

life

# brain broke
