# .NET Core 2.0 / 2.1 debugging

This is a design for the .NET Core 2.0 and 2.1 missing debugging feature.

### What is the problem

Currently SAM CLI does not provide debugging support for .NET Core 2.0 and 2.1 because `dotnet` command does **not** provide _start and wait for the debugger_ out of the box and neither does current AWS Lambda runner has debugging support flag or anything. Apart from that .NET remote debugger ([vsdbg](https://aka.ms/getvsdbgsh)) could not attach via port, but instead only by PID of the running program from within the **target** machine (Docker container). To debug the app, customer can use `docker` pipe, and for that we need the exact container name (which must be the same for each run or predefined for the customer) to attach to, or some mechanism to provide piping support via proxy and expose the port (requires much more effort and additional investigation). 

And let's break it down to the checklist

* Put the `vsdbg` on the Docker container;
* Add _"wait for the debugger"_ flag in runner program and implement corresponding functionality;
* Implement corresponding container entry point override in SAM to support invoking the runner with this flag **on**.
* Provide instructions for the customer of how to configure VS Code and VS to attach.

### What will be changed

Runner program for .NET core [2.0](https://github.com/lambci/docker-lambda/blob/master/dotnetcore2.0/run/MockBootstraps/Program.cs) and [2.1](https://github.com/lambci/docker-lambda/blob/master/dotnetcore2.1/run/MockBootstraps/Program.cs) in another [repo](https://github.com/lambci/docker-lambda) to support waiting for the debugger to attach. Already have [PR](https://github.com/lambci/docker-lambda/pull/130) (guys and @mhart - reviewers wanted :)). I think we should provide new `sam local` flag  `--container-name` which will assign desired name to the container with the Lambda runtime to simplify `docker exec` experience from VS Code later.

### Success Criteria

1. Provide handy script to get the `vsdbg` via downloading it to the .NET Lambda runtime container, installing it and getting through the mounting (or manual instructions to achieve the above results). After that user would be able to provide it to SAM via `--debugger-path`;
2. Provide ready-to-go `launch.json` configuration for attaching to the Lambda function via VSCode;
3. Customer should be able to easily debug .NET Core 2.0 and 2.1 apps on VS Code (minimal requirement).

### Out-of-Scope

Visual Studio 2017 (can be a target, but it has some other very different Docker container debugging support - needs additional investigation). Help in this area is highly appreciated.

### User Experience Walkthrough

##### 1. Getting the debugger locally

At first, user should be able to get and install `vsdbg` on their machine easily. For this we should provide the script for them to invoke, which will effectively run the .NET Lambda runtime Docker container with mounted via `bind` path to get the debugger on the **host** machine. In this container following: `curl -sSL https://aka.ms/getvsdbgsh | bash /dev/stdin -v latest -l /vsdbg`  should be run to get and install required debugger (specifically built for this container). Later SAM will mount this same folder with the debugger to the target running container. 

Instead of script we can certainly provide manual instructions of how to do the above stuff step-by-step as it is now done for golang debugger. _Feedback appreciated_.

Customer should go through this step **only once** to set up the debugger.

##### 2. Publishing the code

Customer should be informed, that in order to have the best debugging experience app must be published in `Debug` configuration by supplying `-c Debug` flag for `dotnet publish` command. 

_For example:_

```sh
dotnet publish -c Debug -o out

# Or via container
docker run --rm --mount src=$(pwd),dst=/var/task,type=bind lambci/lambda:build-dotnetcore2.1 dotnet publish -c Debug -o out
```

##### 3. Attaching

Customer will use ready-to-go `launch.json` debug configuration for VS Code, fill in the container name for the `docker exec` and supply this name to SAM.

_For example:_

```sh
sam local invoke --event event.json -d 6000 --debugger-path ~/vsdbg --container-name debugger "MyFunction"
```

After invoking the function in command line, customer will see:

```
Attach to processId: 1.
Waiting for the debugger to attach...
```

After that user should just conveniently click the _start debugging_ button with our ".NET Core Docker attach" configuration. 

## Implementation

### CLI Changes

The only change I am proposing is to add `--container-name` to specify the exact name for the container which would be run by SAM, so the user will have consistent attaching experience. And overall this flag could be of some use for customers. 

### Design 

##### Supplying debugger

We will have pretty similar approach to what GO is now doing. Customer will get the `vsdbg` on their machine and supply it to SAM via `--debugger-path` . So everything for the first step is already implemented and we will happily reuse that mechanism.

##### Runner with debugging support

As for the debugging support for the runner, unfortunately `dotnet` command does not support _"start and wait"_ configuration out of the box. Neither does C# provide any event which notifies, that debugger was attached. Therefore we will implement custom mechanism for that. 

During the discussion in this related [issue](https://github.com/awslabs/aws-sam-cli/issues/568) it was decided to go with infinite loop approach. It means that program will query [Debugger.IsAttached](https://docs.microsoft.com/en-us/dotnet/api/system.diagnostics.debugger.isattached?view=netcore-2.0) property with some interval (for now it is 50ms - which seems instantaneous for the user), also we have timeout for this loop which is 10 minutes for now (thanks for shaping that out, @mikemorain, @sanathkr). Interval and timeout are **open** for suggestions and edits.

_Examine the code from open [PR](https://github.com/lambci/docker-lambda/pull/130/files):_

```c#
public static bool TryWaitForAttaching(TimeSpan queryInterval, TimeSpan timeout)
{
	var stopwatch = Stopwatch.StartNew();
    
    while (!Debugger.IsAttached)
    {
    	if (stopwatch.Elapsed > timeout)
        {
        	return false;
        }
        
        Task.Delay(queryInterval).Wait();
    }
    
    return true;
}
```

Also for this program `-d` flag was added along with `_SHOULD_WAIT_FOR_DEBUGGER` additional environment variable, so if either of those set, the runner will wait for the debugger to attach.

##### Attaching

Now, as our runner supports waiting for the debugger to attach, the only thing left to do is actually attach to the `dotnet` process with our Lambda **inside** the Docker container. For that I suggest using remote `dotnet` [debugging support](https://github.com/OmniSharp/omnisharp-vscode/wiki/Attaching-to-remote-processes) from VS Code C# extension. We will take advantage of its `pipeTransport` feature. 

Configuration process goes like that: 

1. Set `request: attach` since we are attaching to already running .NET application;
2. Set `pipeProgram` to `docker` (no need for SSH luckily);
3. Use `exec -i <container name>` as `pipeArgs` to step inside the running container;
4. Specify `debuggerPath` as **"/tmp/lambci_debug_files/vsdbg"** (this path reflects current mounting point for `--debugger-path` , refer to this [PR](https://github.com/awslabs/aws-sam-cli/pull/565/files) for more details);
5. Set `quoteArgs` to `False` and let the Docker accept arguments correctly (without the need for `sh`);
6. Set `processId` to 1 as Docker always assigns PID 1 to entry point executables.
7. `sourceFileMap` is used for mapping breakpoints. `/var/task` is the place, where customer's code is being mounted to.

_Examine sample launch.json configuration_

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": ".NET Core Docker Attach",
            "type": "coreclr",
            "request": "attach",
            "processId": "1",
            "pipeTransport": {
                "pipeProgram": "docker",
                "pipeArgs": [ "exec -i <container name>"],
                "debuggerPath": "/tmp/lambci_debug_files/vsdbg",
                "pipeCwd": "${workspaceRoot}",
                "quoteArgs": false
            },

            "sourceFileMap": {
                "/var/task": "${workspaceRoot}"
            }
        }
    ]
}
```

##### Container name caveat

With this `launch.json` in place the only caveat left is the container name to step into. As for now, SAM will not assign consistent names for started containers, and neither it provides the way for the user to supply that name. So my proposal is to create _new flag_ for `sam local` command -  `--container-name` which will provide the user a way to specify the name for the container when it runs. This is a required configuration since user needs consistent naming to have usable attaching experience. SAM will use provided name and add it to `container.start()` configuration.

### Open questions

1. `--container-name` - does this option make sense to you, guys, maybe you have some thoughts of how to it better without exposing the ability to assign the name to the lambda container. As for me, I think this option is more than handy, and does not uncover additional implementation details, as the user is now already well aware, that his function is invoked inside Docker container. Maybe we want to have some environment variable too? Will we include that in `.samrc`? 

2. A bit off-topic, but still, has someone else encountered the problem with python 3.7.1 ? As it now does not flush the `stdout` and `stderr` from the running container immediately but rather after SAM ends the invocation, and user does not see _"waiting for the debugger to attach..."_ message. 

   _From SAM code - container.py:_

   ```python
    for frame_type, data in output_itr:
               #LOG.debug("Next frame")
               if frame_type == Container._STDOUT_FRAME_TYPE and stdout:
                   # Frame type 1 is stdout data.
                   stdout.write(data)
                   # with this in place, everything works fine
                   stdout.flush()
   
               elif frame_type == Container._STDERR_FRAME_TYPE and stderr:
                   # Frame type 2 is stderr data.
                   stderr.write(data)
                   # with this in place, everything works fine
                   stderr.flush()
   ```

   As you see above with flush, everything works. Without it all is buffered, help needed, maybe this [link](https://docs.python.org/3/using/cmdline.html#cmdoption-u) will give something (see note for python 3.7),

3. Help needed in investigation of how to adopt that approach for VS 2017. See this [link](https://github.com/Microsoft/MIEngine/wiki/Offroad-Debugging-of-.NET-Core-on-Linux---OSX-from-Visual-Studio) for some information. Maybe we can try to use Docker as a pipe there too.
4. Docker in VS Code reports _"The pipe program 'docker' exited unexpectedly with code 137."_ after stopping or hitting continue which leads to quitting the program. It seems, that 137 is **killed** exit code, which seems a bit strange, maybe you guys, have some ideas on that? Haven't investigated yet.



### Tasks breakdown

- [x] Submit PR with the design doc;
- [x] Submit PR with runner program improvements;
- [x] Close the question with `--container-name` option;
- [x] Implement required changes in SAM;
- [x] Write tests;
- [x] Submit PR with this changes to SAM repo.
- [ ] Merge [PR](https://github.com/lambci/docker-lambda/pull/130) to lambci/docker-lambda [repo](https://github.com/lambci/docker-lambda) **WIP** 🚨 blocker;
- [ ] Merge [PR](https://github.com/awslabs/aws-sam-cli/pull/774) to SAM repo **WIP**.