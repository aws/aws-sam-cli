///////////////////////////////////////////////////////////////////////////////
// ARGUMENTS
///////////////////////////////////////////////////////////////////////////////

var target = Argument<string>("target", "Default");
var configuration = Argument<string>("configuration", "Release");
var verbosity = Argument<string>("verbosity", "Minimal");

///////////////////////////////////////////////////////////////////////////////
// GLOBAL VARIABLES
///////////////////////////////////////////////////////////////////////////////

var sourceDir = Directory("./src");

var solutions = GetFiles("./**/*.sln");
var projects = new []
{
    sourceDir.Path + "/HelloWorld/HelloWorld.csproj",
};

// BUILD OUTPUT DIRECTORIES
var artifactsDir = Directory("./artifacts");
var publishDir = Directory("./publish/");

// VERBOSITY
var dotNetCoreVerbosity = Cake.Common.Tools.DotNetCore.DotNetCoreVerbosity.Normal;
if (!Enum.TryParse(verbosity, true, out dotNetCoreVerbosity))
{	
    dotNetCoreVerbosity = Cake.Common.Tools.DotNetCore.DotNetCoreVerbosity.Normal;
    Warning(
        "Verbosity could not be parsed into type 'Cake.Common.Tools.DotNetCore.DotNetCoreVerbosity'. Defaulting to {0}", 
        dotNetCoreVerbosity); 
}

///////////////////////////////////////////////////////////////////////////////
// COMMON FUNCTION DEFINITIONS
///////////////////////////////////////////////////////////////////////////////

string GetProjectName(string project)
{
    return project
        .Split(new [] {'/'}, StringSplitOptions.RemoveEmptyEntries)
        .Last()
        .Replace(".csproj", string.Empty);
}

///////////////////////////////////////////////////////////////////////////////
// SETUP / TEARDOWN
///////////////////////////////////////////////////////////////////////////////

Setup(ctx =>
{
    // Executed BEFORE the first task.
	EnsureDirectoryExists(artifactsDir);
	EnsureDirectoryExists(publishDir);
    Information("Running tasks...");
});

Teardown(ctx =>
{
    // Executed AFTER the last task.
    Information("Finished running tasks.");
});

///////////////////////////////////////////////////////////////////////////////
// TASK DEFINITIONS
///////////////////////////////////////////////////////////////////////////////

Task("Clean")
    .Description("Cleans all directories that are used during the build process.")
    .Does(() =>
    {
        foreach(var solution in solutions)
        {
            Information("Cleaning {0}", solution.FullPath);
            CleanDirectories(solution.FullPath + "/**/bin/" + configuration);
            CleanDirectories(solution.FullPath + "/**/obj/" + configuration);
            Information("{0} was clean.", solution.FullPath);
        }

        CleanDirectory(artifactsDir);
        CleanDirectory(publishDir);
    });

Task("Restore")
	.Description("Restores all the NuGet packages that are used by the specified solution.")
	.Does(() => 
    {
        var settings = new DotNetCoreRestoreSettings
        {
            DisableParallel = false,
            NoCache = true,
            Verbosity = dotNetCoreVerbosity
        };
        
        foreach(var solution in solutions)
        {
            Information("Restoring NuGet packages for '{0}'...", solution);
            DotNetCoreRestore(solution.FullPath, settings);
            Information("NuGet packages restored for '{0}'.", solution);
        }
    });

Task("Build")
	.Description("Builds all the different parts of the project.")
	.Does(() => 
    {
        var msBuildSettings = new DotNetCoreMSBuildSettings 
        {
            TreatAllWarningsAs = MSBuildTreatAllWarningsAs.Error,
            Verbosity = dotNetCoreVerbosity
        };

        var settings = new DotNetCoreBuildSettings 
        {
            Configuration = configuration,
            MSBuildSettings = msBuildSettings,
            NoRestore = true
        };

        foreach(var solution in solutions)
        {
            Information("Building '{0}'...", solution);
            DotNetCoreBuild(solution.FullPath, settings);
            Information("'{0}' has been built.", solution);
        }
    });

Task("Test-Unit")
	.Description("Tests all the different parts of the project.")
	.Does(() => 
    {
        var settings = new DotNetCoreTestSettings
        {
            Configuration = configuration,
            NoRestore = true,
            NoBuild = true
        };
        
        var projectFiles = GetFiles("./test/**/*.csproj");
        foreach(var file in projectFiles)
        {
            Information("Testing '{0}'...", file);
            DotNetCoreTest(file.FullPath, settings);
            Information("'{0}' has been tested.", file);
        }
    });

Task("Publish")
    .Description("Publish the Lambda Functions.")
    .Does(() => 
    {
        foreach(var project in projects)
        {
			var projectName =  project
				.Split(new [] {'/'}, StringSplitOptions.RemoveEmptyEntries)
				.Last()
				.Replace(".csproj", string.Empty);

            var outputDirectory = System.IO.Path.Combine(publishDir, projectName);

            var msBuildSettings = new DotNetCoreMSBuildSettings 
            {
                TreatAllWarningsAs = MSBuildTreatAllWarningsAs.Error,
                Verbosity = dotNetCoreVerbosity
            };

			var settings = new DotNetCorePublishSettings
			{
				Configuration = configuration,
				MSBuildSettings = msBuildSettings,
				NoRestore = true,
				OutputDirectory = outputDirectory,
				Verbosity = dotNetCoreVerbosity
			};

            Information("Publishing '{0}'...", projectName);
            DotNetCorePublish(project, settings); 
            Information("'{0}' has been published.", projectName);
        }
    });

Task("Pack")
	.Description("Packs all the different parts of the project.")
	.Does(() => 
    {
		foreach(var project in projects)
        {
			var projectName = GetProjectName(project);

			Information("Packing '{0}'...", projectName);
			var path = System.IO.Path.Combine(publishDir, projectName);
			var files = GetFiles(path + "/*.*");
			Zip(
				path, 
				System.IO.Path.Combine(artifactsDir, $"{projectName}.zip"),
				files);
			Information("'{0}' has been packed.", projectName);
        }
    });

Task("Run-Local")
	.Description("Runs all the acceptance tests locally.")
	.Does(() => 
    {
        var settings = new ProcessSettings
        { 
            Arguments = "local invoke \"HelloWorld\" -e event.json",
        };
        
        Information("Starting the SAM local...");
        using(var process = StartAndReturnProcess("sam", settings))
        {
            process.WaitForExit();
            Information("Exit code: {0}", process.GetExitCode());
        }
        Information("SAM local has finished.");
    });

///////////////////////////////////////////////////////////////////////////////
// TARGETS
///////////////////////////////////////////////////////////////////////////////

Task("Package")
    .Description("This is the task which will run if target Package is passed in.")
    .IsDependentOn("Clean")
    .IsDependentOn("Restore")
    .IsDependentOn("Build")
    .IsDependentOn("Test-Unit")
    .IsDependentOn("Publish")
    .IsDependentOn("Pack")
    .Does(() => { Information("Package target ran."); });

Task("Test")
    .Description("This is the task which will run if target Test is passed in.")
    .IsDependentOn("Clean")
    .IsDependentOn("Restore")
    .IsDependentOn("Build")
    .IsDependentOn("Test-Unit")
    .Does(() => { Information("Test target ran."); });

Task("Run")
    .Description("This is the task which will run if target Run is passed in.")
    .IsDependentOn("Clean")
    .IsDependentOn("Restore")
    .IsDependentOn("Build")
    .IsDependentOn("Test-Unit")
    .IsDependentOn("Publish")
    .IsDependentOn("Pack")
    .IsDependentOn("Run-Local")
    .Does(() => { Information("Run target ran."); });
    
Task("Default")
    .Description("This is the default task which will run if no specific target is passed in.")
    .IsDependentOn("Package");

///////////////////////////////////////////////////////////////////////////////
// EXECUTION
///////////////////////////////////////////////////////////////////////////////

RunTarget(target);
